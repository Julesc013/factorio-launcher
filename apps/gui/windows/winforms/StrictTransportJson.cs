// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    internal static class StrictTransportJson
    {
        internal static Dictionary<string, object> ParseObject(string text, int maximumCharacters)
        {
            if (text == null) throw new InvalidDataException("Response JSON is absent.");
            if (text.Length > maximumCharacters)
                throw new InvalidDataException("Response JSON exceeds its decoded character budget.");
            Parser parser = new Parser(text);
            parser.ParseRootObject();
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = maximumCharacters;
            Dictionary<string, object> value =
                serializer.DeserializeObject(text) as Dictionary<string, object>;
            if (value == null) throw new InvalidDataException("Response JSON root must be an object.");
            return value;
        }

        private sealed class Parser
        {
            private readonly string text;
            private int offset;

            internal Parser(string text)
            {
                this.text = text;
            }

            internal void ParseRootObject()
            {
                SkipWhitespace();
                if (Peek() != '{') throw Error("Response JSON root must be an object.");
                ParseObject();
                SkipWhitespace();
                if (offset != text.Length)
                    throw Error("Response JSON contains trailing data or multiple values.");
            }

            private void ParseValue()
            {
                char ch = Peek();
                if (ch == '{') ParseObject();
                else if (ch == '[') ParseArray();
                else if (ch == '"') ParseString();
                else if (ch == '-' || (ch >= '0' && ch <= '9')) ParseNumber();
                else if (Match("true") || Match("false") || Match("null")) return;
                else throw Error("Response JSON contains an invalid value.");
            }

            private void ParseObject()
            {
                Expect('{');
                SkipWhitespace();
                HashSet<string> members = new HashSet<string>(StringComparer.Ordinal);
                if (Consume('}')) return;
                while (true)
                {
                    if (Peek() != '"') throw Error("JSON object member name must be a string.");
                    string name = ParseString();
                    if (!members.Add(name))
                        throw Error("Response JSON contains duplicate member: " + name);
                    SkipWhitespace();
                    Expect(':');
                    SkipWhitespace();
                    ParseValue();
                    SkipWhitespace();
                    if (Consume('}')) return;
                    Expect(',');
                    SkipWhitespace();
                }
            }

            private void ParseArray()
            {
                Expect('[');
                SkipWhitespace();
                if (Consume(']')) return;
                while (true)
                {
                    ParseValue();
                    SkipWhitespace();
                    if (Consume(']')) return;
                    Expect(',');
                    SkipWhitespace();
                }
            }

            private string ParseString()
            {
                Expect('"');
                StringBuilder value = new StringBuilder();
                while (offset < text.Length)
                {
                    char ch = text[offset++];
                    if (ch == '"') return value.ToString();
                    if (ch < 0x20) throw Error("JSON string contains an unescaped control character.");
                    if (ch == '\\')
                    {
                        if (offset >= text.Length) throw Error("JSON string escape is incomplete.");
                        char escaped = text[offset++];
                        if (escaped == '"' || escaped == '\\' || escaped == '/') value.Append(escaped);
                        else if (escaped == 'b') value.Append('\b');
                        else if (escaped == 'f') value.Append('\f');
                        else if (escaped == 'n') value.Append('\n');
                        else if (escaped == 'r') value.Append('\r');
                        else if (escaped == 't') value.Append('\t');
                        else if (escaped == 'u') AppendUnicodeEscape(value);
                        else throw Error("JSON string contains an invalid escape.");
                    }
                    else if (Char.IsHighSurrogate(ch))
                    {
                        if (offset >= text.Length || !Char.IsLowSurrogate(text[offset]))
                            throw Error("JSON string contains an unpaired high surrogate.");
                        value.Append(ch);
                        value.Append(text[offset++]);
                    }
                    else if (Char.IsLowSurrogate(ch))
                    {
                        throw Error("JSON string contains an unpaired low surrogate.");
                    }
                    else
                    {
                        value.Append(ch);
                    }
                }
                throw Error("JSON string is unterminated.");
            }

            private void AppendUnicodeEscape(StringBuilder value)
            {
                char first = ParseHexCodeUnit();
                if (Char.IsHighSurrogate(first))
                {
                    if (offset + 2 > text.Length || text[offset] != '\\' || text[offset + 1] != 'u')
                        throw Error("JSON unicode escape contains an unpaired high surrogate.");
                    offset += 2;
                    char second = ParseHexCodeUnit();
                    if (!Char.IsLowSurrogate(second))
                        throw Error("JSON unicode escape contains an invalid surrogate pair.");
                    value.Append(first);
                    value.Append(second);
                }
                else if (Char.IsLowSurrogate(first))
                {
                    throw Error("JSON unicode escape contains an unpaired low surrogate.");
                }
                else
                {
                    value.Append(first);
                }
            }

            private char ParseHexCodeUnit()
            {
                if (offset + 4 > text.Length) throw Error("JSON unicode escape is incomplete.");
                int number = 0;
                for (int index = 0; index < 4; ++index)
                {
                    char ch = text[offset++];
                    int digit;
                    if (ch >= '0' && ch <= '9') digit = ch - '0';
                    else if (ch >= 'a' && ch <= 'f') digit = ch - 'a' + 10;
                    else if (ch >= 'A' && ch <= 'F') digit = ch - 'A' + 10;
                    else throw Error("JSON unicode escape contains a non-hexadecimal digit.");
                    number = (number * 16) + digit;
                }
                return (char)number;
            }

            private void ParseNumber()
            {
                Consume('-');
                if (Consume('0'))
                {
                    if (IsDigit(Peek())) throw Error("JSON number contains a leading zero.");
                }
                else
                {
                    RequireDigit();
                    while (IsDigit(Peek())) offset++;
                }
                if (Consume('.'))
                {
                    RequireDigit();
                    while (IsDigit(Peek())) offset++;
                }
                char exponent = Peek();
                if (exponent == 'e' || exponent == 'E')
                {
                    offset++;
                    if (Peek() == '+' || Peek() == '-') offset++;
                    RequireDigit();
                    while (IsDigit(Peek())) offset++;
                }
            }

            private void RequireDigit()
            {
                if (!IsDigit(Peek())) throw Error("JSON number is incomplete.");
                offset++;
            }

            private bool Match(string literal)
            {
                if (offset + literal.Length > text.Length) return false;
                if (!String.Equals(
                    text.Substring(offset, literal.Length), literal, StringComparison.Ordinal))
                    return false;
                offset += literal.Length;
                return true;
            }

            private void SkipWhitespace()
            {
                while (offset < text.Length)
                {
                    char ch = text[offset];
                    if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') return;
                    offset++;
                }
            }

            private char Peek()
            {
                return offset < text.Length ? text[offset] : '\0';
            }

            private bool Consume(char expected)
            {
                if (Peek() != expected) return false;
                offset++;
                return true;
            }

            private void Expect(char expected)
            {
                if (!Consume(expected))
                    throw Error("Expected '" + expected.ToString() + "'.");
            }

            private static bool IsDigit(char ch)
            {
                return ch >= '0' && ch <= '9';
            }

            private InvalidDataException Error(string message)
            {
                return new InvalidDataException(message + " Offset " + offset.ToString(CultureInfo.InvariantCulture) + ".");
            }
        }
    }
}
