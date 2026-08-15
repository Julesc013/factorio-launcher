// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;

namespace FacMan.WinForms
{
    internal static class ProviderIdentity
    {
        private const string ResourceName = "FacMan.WinForms.ProviderIdentity.v1";
        private const int MaximumBytes = 512;

        internal static readonly string Classification;
        internal static readonly string UniversalLauncherRevision;
        internal static readonly string UniversalSetupRevision;

        static ProviderIdentity()
        {
            Assembly assembly = typeof(ProviderIdentity).Assembly;
            using (Stream stream = assembly.GetManifestResourceStream(ResourceName))
            {
                if (stream == null || stream.Length <= 0 || stream.Length > MaximumBytes)
                    throw new InvalidDataException("The WinForms provider identity resource is absent or unbounded.");
                byte[] bytes = new byte[(int)stream.Length];
                int offset = 0;
                while (offset < bytes.Length)
                {
                    int count = stream.Read(bytes, offset, bytes.Length - offset);
                    if (count <= 0)
                        throw new EndOfStreamException("The WinForms provider identity resource is truncated.");
                    offset += count;
                }
                string text = new UTF8Encoding(false, true).GetString(bytes);
                text = text.TrimEnd('\r', '\n');
                if (text.IndexOfAny(new char[] { '\r', '\n', '\0' }) >= 0)
                    throw new InvalidDataException("The WinForms provider identity must be one strict line.");
                Dictionary<string, string> fields = Parse(text);
                Classification = fields["classification"];
                UniversalLauncherRevision = Revision(fields["universal_launcher"]);
                UniversalSetupRevision = Revision(fields["universal_setup"]);
                if (Classification != "canonical" &&
                    Classification != "repaired_provider_canary")
                    throw new InvalidDataException("The WinForms provider identity classification is invalid.");
            }
        }

        private static Dictionary<string, string> Parse(string text)
        {
            string[] expected = new string[] {
                "classification", "universal_launcher", "universal_setup"
            };
            string[] segments = text.Split(';');
            if (segments.Length != expected.Length)
                throw new InvalidDataException("The WinForms provider identity has the wrong field count.");
            Dictionary<string, string> fields = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int index = 0; index < expected.Length; ++index)
            {
                int equals = segments[index].IndexOf('=');
                if (equals <= 0 || equals == segments[index].Length - 1)
                    throw new InvalidDataException("The WinForms provider identity has an empty field.");
                string key = segments[index].Substring(0, equals);
                string value = segments[index].Substring(equals + 1);
                if (key != expected[index] || fields.ContainsKey(key))
                    throw new InvalidDataException("The WinForms provider identity fields are out of order.");
                fields.Add(key, value);
            }
            return fields;
        }

        private static string Revision(string value)
        {
            if (value.Length != 40)
                throw new InvalidDataException("The WinForms provider revision has the wrong length.");
            foreach (char character in value)
            {
                if (!((character >= '0' && character <= '9') ||
                      (character >= 'a' && character <= 'f')))
                    throw new InvalidDataException("The WinForms provider revision is not lowercase hexadecimal.");
            }
            return value;
        }
    }
}
