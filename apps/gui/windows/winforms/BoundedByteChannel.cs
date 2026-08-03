// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.IO;
using System.Threading.Tasks;

namespace FacMan.WinForms
{
    internal sealed class BoundedByteReadResult
    {
        internal BoundedByteReadResult(byte[] bytes, bool exceeded, Exception error)
        {
            Bytes = bytes ?? new byte[0];
            Exceeded = exceeded;
            Error = error;
        }

        internal byte[] Bytes { get; private set; }
        internal bool Exceeded { get; private set; }
        internal Exception Error { get; private set; }
    }

    internal sealed class BoundedByteChannel
    {
        private readonly TaskCompletionSource<bool> limitExceeded;

        private BoundedByteChannel(
            Task<BoundedByteReadResult> completion,
            TaskCompletionSource<bool> limitExceeded)
        {
            Completion = completion;
            this.limitExceeded = limitExceeded;
        }

        internal Task<BoundedByteReadResult> Completion { get; private set; }
        internal Task LimitExceeded { get { return limitExceeded.Task; } }

        internal static BoundedByteChannel Start(Stream stream, int maximumBytes)
        {
            if (stream == null) throw new ArgumentNullException("stream");
            if (maximumBytes <= 0) throw new ArgumentOutOfRangeException("maximumBytes");
            TaskCompletionSource<bool> signal = new TaskCompletionSource<bool>();
            Task<BoundedByteReadResult> completion = Task.Run(
                delegate { return ReadAndDrain(stream, maximumBytes, signal); });
            return new BoundedByteChannel(completion, signal);
        }

        private static BoundedByteReadResult ReadAndDrain(
            Stream stream,
            int maximumBytes,
            TaskCompletionSource<bool> signal)
        {
            MemoryStream retained = new MemoryStream(Math.Min(maximumBytes, 64 * 1024));
            byte[] buffer = new byte[8192];
            bool exceeded = false;
            try
            {
                int count;
                while ((count = stream.Read(buffer, 0, buffer.Length)) > 0)
                {
                    int remaining = maximumBytes - checked((int)retained.Length);
                    int keep = Math.Min(Math.Max(remaining, 0), count);
                    if (keep > 0) retained.Write(buffer, 0, keep);
                    if (count > keep && !exceeded)
                    {
                        exceeded = true;
                        signal.TrySetResult(true);
                    }
                }
                return new BoundedByteReadResult(retained.ToArray(), exceeded, null);
            }
            catch (Exception ex)
            {
                return new BoundedByteReadResult(retained.ToArray(), exceeded, ex);
            }
            finally
            {
                retained.Dispose();
            }
        }
    }
}
