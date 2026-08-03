// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32.SafeHandles;

namespace FacMan.WinForms
{
    internal sealed class WindowsContainedProcess : IDisposable
    {
        private const uint CreateSuspended = 0x00000004;
        private const uint CreateNoWindow = 0x08000000;
        private const uint StartfUseStdHandles = 0x00000100;
        private const uint HandleFlagInherit = 0x00000001;
        private const uint JobObjectLimitKillOnJobClose = 0x00002000;
        private const int JobInfoBasicAccounting = 1;
        private const int JobInfoExtendedLimit = 9;
        private const uint Infinite = 0xffffffff;

        private IntPtr processHandle;
        private IntPtr threadHandle;
        private IntPtr jobHandle;
        private bool resumed;
        private bool disposed;

        private WindowsContainedProcess(
            IntPtr processHandle,
            IntPtr threadHandle,
            IntPtr jobHandle,
            FileStream standardInput,
            FileStream standardOutput,
            FileStream standardError,
            int processId)
        {
            this.processHandle = processHandle;
            this.threadHandle = threadHandle;
            this.jobHandle = jobHandle;
            StandardInput = standardInput;
            StandardOutput = standardOutput;
            StandardError = standardError;
            ProcessId = processId;
            ExitTask = Task.Run(delegate
            {
                uint wait = WaitForSingleObject(processHandle, Infinite);
                if (wait != 0) throw new Win32Exception(Marshal.GetLastWin32Error());
                uint exitCode;
                if (!GetExitCodeProcess(processHandle, out exitCode))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return unchecked((int)exitCode);
            });
        }

        internal Stream StandardInput { get; private set; }
        internal Stream StandardOutput { get; private set; }
        internal Stream StandardError { get; private set; }
        internal int ProcessId { get; private set; }
        internal Task<int> ExitTask { get; private set; }

        internal static WindowsContainedProcess StartSuspended(
            string executable,
            string arguments,
            Action revalidateImmediatelyBeforeCreateProcess,
            Action<IntPtr> validateCreatedSuspendedProcess)
        {
            if (Environment.OSVersion.Platform != PlatformID.Win32NT)
                throw new PlatformNotSupportedException("WinForms containment requires Windows.");
            if (String.IsNullOrWhiteSpace(executable))
                throw new ArgumentException("Executable path is required.", "executable");

            IntPtr childInputRead = IntPtr.Zero;
            IntPtr parentInputWrite = IntPtr.Zero;
            IntPtr parentOutputRead = IntPtr.Zero;
            IntPtr childOutputWrite = IntPtr.Zero;
            IntPtr parentErrorRead = IntPtr.Zero;
            IntPtr childErrorWrite = IntPtr.Zero;
            IntPtr processHandle = IntPtr.Zero;
            IntPtr threadHandle = IntPtr.Zero;
            IntPtr jobHandle = IntPtr.Zero;
            FileStream input = null;
            FileStream output = null;
            FileStream error = null;
            try
            {
                SecurityAttributes security = new SecurityAttributes();
                security.Length = Marshal.SizeOf(typeof(SecurityAttributes));
                security.InheritHandle = true;
                CreatePipeChecked(out childInputRead, out parentInputWrite, security);
                CreatePipeChecked(out parentOutputRead, out childOutputWrite, security);
                CreatePipeChecked(out parentErrorRead, out childErrorWrite, security);
                SetNoInherit(parentInputWrite);
                SetNoInherit(parentOutputRead);
                SetNoInherit(parentErrorRead);

                StartupInfo startup = new StartupInfo();
                startup.Size = Marshal.SizeOf(typeof(StartupInfo));
                startup.Flags = StartfUseStdHandles;
                startup.StandardInput = childInputRead;
                startup.StandardOutput = childOutputWrite;
                startup.StandardError = childErrorWrite;
                ProcessInformation process;
                StringBuilder commandLine = new StringBuilder(
                    QuoteCommandLineArgument(executable) + " " + (arguments ?? String.Empty));
                if (revalidateImmediatelyBeforeCreateProcess == null)
                    throw new ArgumentNullException("revalidateImmediatelyBeforeCreateProcess");
                if (validateCreatedSuspendedProcess == null)
                    throw new ArgumentNullException("validateCreatedSuspendedProcess");
                revalidateImmediatelyBeforeCreateProcess();
                bool created = CreateProcess(
                    executable,
                    commandLine,
                    IntPtr.Zero,
                    IntPtr.Zero,
                    true,
                    CreateSuspended | CreateNoWindow,
                    IntPtr.Zero,
                    null,
                    ref startup,
                    out process);
                if (!created) throw new Win32Exception(Marshal.GetLastWin32Error());
                processHandle = process.Process;
                threadHandle = process.Thread;
                validateCreatedSuspendedProcess(processHandle);

                jobHandle = CreateJobObject(IntPtr.Zero, null);
                if (jobHandle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
                ConfigureKillOnClose(jobHandle);
                if (!AssignProcessToJobObject(jobHandle, processHandle))
                    throw new Win32Exception(Marshal.GetLastWin32Error());

                CloseNative(ref childInputRead);
                CloseNative(ref childOutputWrite);
                CloseNative(ref childErrorWrite);
                input = CreateAsyncStream(ref parentInputWrite, FileAccess.Write);
                output = CreateAsyncStream(ref parentOutputRead, FileAccess.Read);
                error = CreateAsyncStream(ref parentErrorRead, FileAccess.Read);
                return new WindowsContainedProcess(
                    processHandle,
                    threadHandle,
                    jobHandle,
                    input,
                    output,
                    error,
                    unchecked((int)process.ProcessId));
            }
            catch
            {
                if (jobHandle != IntPtr.Zero) TerminateJobObject(jobHandle, 1);
                else if (processHandle != IntPtr.Zero) TerminateProcess(processHandle, 1);
                if (input != null) input.Dispose();
                if (output != null) output.Dispose();
                if (error != null) error.Dispose();
                CloseNative(ref childInputRead);
                CloseNative(ref parentInputWrite);
                CloseNative(ref parentOutputRead);
                CloseNative(ref childOutputWrite);
                CloseNative(ref parentErrorRead);
                CloseNative(ref childErrorWrite);
                CloseNative(ref threadHandle);
                CloseNative(ref processHandle);
                CloseNative(ref jobHandle);
                throw;
            }
        }

        internal void Resume()
        {
            ThrowIfDisposed();
            if (resumed) return;
            uint previous = ResumeThread(threadHandle);
            if (previous == UInt32.MaxValue)
                throw new Win32Exception(Marshal.GetLastWin32Error());
            resumed = true;
            CloseNative(ref threadHandle);
        }

        internal bool TerminateTree()
        {
            if (disposed || jobHandle == IntPtr.Zero) return false;
            return TerminateJobObject(jobHandle, 1);
        }

        internal Task<bool> WaitForTreeEmptyAsync(DateTime deadlineUtc)
        {
            return Task.Run(delegate
            {
                while (DateTime.UtcNow < deadlineUtc)
                {
                    if (ActiveProcessCount() == 0) return true;
                    Thread.Sleep(10);
                }
                return ActiveProcessCount() == 0;
            });
        }

        internal void CloseInput()
        {
            Stream input = StandardInput;
            StandardInput = Stream.Null;
            if (input != null && input != Stream.Null) input.Dispose();
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            if (jobHandle != IntPtr.Zero) TerminateJobObject(jobHandle, 1);
            Stream input = StandardInput;
            Stream output = StandardOutput;
            Stream error = StandardError;
            StandardInput = Stream.Null;
            StandardOutput = Stream.Null;
            StandardError = Stream.Null;
            if (input != null && input != Stream.Null) input.Dispose();
            if (output != null && output != Stream.Null) output.Dispose();
            if (error != null && error != Stream.Null) error.Dispose();
            CloseNative(ref threadHandle);
            CloseNative(ref processHandle);
            CloseNative(ref jobHandle);
        }

        private uint ActiveProcessCount()
        {
            JobObjectBasicAccountingInformation accounting =
                new JobObjectBasicAccountingInformation();
            int length = Marshal.SizeOf(typeof(JobObjectBasicAccountingInformation));
            IntPtr memory = Marshal.AllocHGlobal(length);
            try
            {
                Marshal.StructureToPtr(accounting, memory, false);
                if (!QueryInformationJobObject(
                    jobHandle,
                    JobInfoBasicAccounting,
                    memory,
                    (uint)length,
                    IntPtr.Zero))
                    return UInt32.MaxValue;
                accounting = (JobObjectBasicAccountingInformation)Marshal.PtrToStructure(
                    memory, typeof(JobObjectBasicAccountingInformation));
                return accounting.ActiveProcesses;
            }
            finally
            {
                Marshal.FreeHGlobal(memory);
            }
        }

        private static void ConfigureKillOnClose(IntPtr job)
        {
            JobObjectExtendedLimitInformation limits = new JobObjectExtendedLimitInformation();
            limits.BasicLimitInformation.LimitFlags = JobObjectLimitKillOnJobClose;
            int length = Marshal.SizeOf(typeof(JobObjectExtendedLimitInformation));
            IntPtr memory = Marshal.AllocHGlobal(length);
            try
            {
                Marshal.StructureToPtr(limits, memory, false);
                if (!SetInformationJobObject(
                    job,
                    JobInfoExtendedLimit,
                    memory,
                    (uint)length))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            finally
            {
                Marshal.FreeHGlobal(memory);
            }
        }

        private static FileStream CreateAsyncStream(ref IntPtr handle, FileAccess access)
        {
            SafeFileHandle safe = new SafeFileHandle(handle, true);
            handle = IntPtr.Zero;
            return new FileStream(safe, access, 8192, false);
        }

        private static void CreatePipeChecked(
            out IntPtr read,
            out IntPtr write,
            SecurityAttributes security)
        {
            if (!CreatePipe(out read, out write, ref security, 0))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        private static void SetNoInherit(IntPtr handle)
        {
            if (!SetHandleInformation(handle, HandleFlagInherit, 0))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        private static string QuoteCommandLineArgument(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private static void CloseNative(ref IntPtr handle)
        {
            IntPtr closing = handle;
            handle = IntPtr.Zero;
            if (closing != IntPtr.Zero && closing != new IntPtr(-1)) CloseHandle(closing);
        }

        private void ThrowIfDisposed()
        {
            if (disposed) throw new ObjectDisposedException("WindowsContainedProcess");
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SecurityAttributes
        {
            internal int Length;
            internal IntPtr SecurityDescriptor;
            [MarshalAs(UnmanagedType.Bool)] internal bool InheritHandle;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct StartupInfo
        {
            internal int Size;
            internal string Reserved;
            internal string Desktop;
            internal string Title;
            internal int X;
            internal int Y;
            internal int XSize;
            internal int YSize;
            internal int XCountChars;
            internal int YCountChars;
            internal int FillAttribute;
            internal uint Flags;
            internal short ShowWindow;
            internal short Reserved2Count;
            internal IntPtr Reserved2;
            internal IntPtr StandardInput;
            internal IntPtr StandardOutput;
            internal IntPtr StandardError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ProcessInformation
        {
            internal IntPtr Process;
            internal IntPtr Thread;
            internal uint ProcessId;
            internal uint ThreadId;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JobObjectBasicAccountingInformation
        {
            internal long TotalUserTime;
            internal long TotalKernelTime;
            internal long ThisPeriodTotalUserTime;
            internal long ThisPeriodTotalKernelTime;
            internal uint TotalPageFaultCount;
            internal uint TotalProcesses;
            internal uint ActiveProcesses;
            internal uint TotalTerminatedProcesses;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JobObjectBasicLimitInformation
        {
            internal long PerProcessUserTimeLimit;
            internal long PerJobUserTimeLimit;
            internal uint LimitFlags;
            internal UIntPtr MinimumWorkingSetSize;
            internal UIntPtr MaximumWorkingSetSize;
            internal uint ActiveProcessLimit;
            internal UIntPtr Affinity;
            internal uint PriorityClass;
            internal uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IoCounters
        {
            internal ulong ReadOperationCount;
            internal ulong WriteOperationCount;
            internal ulong OtherOperationCount;
            internal ulong ReadTransferCount;
            internal ulong WriteTransferCount;
            internal ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JobObjectExtendedLimitInformation
        {
            internal JobObjectBasicLimitInformation BasicLimitInformation;
            internal IoCounters IoInfo;
            internal UIntPtr ProcessMemoryLimit;
            internal UIntPtr JobMemoryLimit;
            internal UIntPtr PeakProcessMemoryUsed;
            internal UIntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CreatePipe(
            out IntPtr readPipe,
            out IntPtr writePipe,
            ref SecurityAttributes pipeAttributes,
            uint size);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcess(
            string applicationName,
            StringBuilder commandLine,
            IntPtr processAttributes,
            IntPtr threadAttributes,
            [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
            uint creationFlags,
            IntPtr environment,
            string currentDirectory,
            ref StartupInfo startupInfo,
            out ProcessInformation processInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr jobAttributes, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(
            IntPtr job,
            int informationClass,
            IntPtr information,
            uint informationLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool QueryInformationJobObject(
            IntPtr job,
            int informationClass,
            IntPtr information,
            uint informationLength,
            IntPtr returnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateJobObject(IntPtr job, uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr process, uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr thread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);
    }
}
