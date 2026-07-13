using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

public class TamilVitsTokenizer
{
    private Dictionary<string, int> encoder = new Dictionary<string, int>();
    private List<string> vocabKeysInOrder = new List<string>(); // preserves original ordering for greedy matching

    public TamilVitsTokenizer(string vocabJsonText)
    {
        ParseVocabJson(vocabJsonText);
    }

    // Minimal parser for a flat {"key": value, ...} JSON object with UTF-8 string keys and integer values
    private void ParseVocabJson(string json)
    {
        int i = 0;
        int n = json.Length;

        void SkipWhitespace() { while (i < n && char.IsWhiteSpace(json[i])) i++; }

        string ParseString()
        {
            var sb = new StringBuilder();
            i++; // skip opening quote
            while (i < n && json[i] != '"')
            {
                if (json[i] == '\\' && i + 1 < n)
                {
                    i++;
                    switch (json[i])
                    {
                        case 'n': sb.Append('\n'); break;
                        case 't': sb.Append('\t'); break;
                        case 'r': sb.Append('\r'); break;
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'u':
                            string hex = json.Substring(i + 1, 4);
                            sb.Append((char)Convert.ToInt32(hex, 16));
                            i += 4;
                            break;
                        default: sb.Append(json[i]); break;
                    }
                }
                else
                {
                    sb.Append(json[i]);
                }
                i++;
            }
            i++; // skip closing quote
            return sb.ToString();
        }

        SkipWhitespace();
        if (json[i] != '{') throw new Exception("Expected '{' at start of vocab.json");
        i++;

        while (true)
        {
            SkipWhitespace();
            if (json[i] == '}') { i++; break; }
            if (json[i] == ',') { i++; SkipWhitespace(); }

            string key = ParseString();
            SkipWhitespace();
            if (json[i] != ':') throw new Exception("Expected ':' after key");
            i++;
            SkipWhitespace();

            int start = i;
            while (i < n && (char.IsDigit(json[i]) || json[i] == '-')) i++;
            int value = int.Parse(json.Substring(start, i - start));

            encoder[key] = value;
            vocabKeysInOrder.Add(key);
        }
    }

    // Faithful port of normalize_text(): greedy vocab-match, else lowercase single char
    private string NormalizeText(string input)
    {
        var result = new StringBuilder();
        int i = 0;
        while (i < input.Length)
        {
            bool foundMatch = false;
            foreach (var word in vocabKeysInOrder)
            {
                if (word.Length > 0 && i + word.Length <= input.Length &&
                    input.Substring(i, word.Length) == word)
                {
                    result.Append(word);
                    i += word.Length;
                    foundMatch = true;
                    break;
                }
            }
            if (!foundMatch)
            {
                result.Append(char.ToLower(input[i]));
                i++;
            }
        }
        return result.ToString();
    }

    // Full pipeline: text -> input_ids array, ready for the model
    public int[] Encode(string text)
    {
        string normalized = NormalizeText(text);

        // Strip any character not in vocab
        var filtered = new StringBuilder();
        foreach (char c in normalized)
        {
            if (encoder.ContainsKey(c.ToString()))
                filtered.Append(c);
        }
        string cleanText = filtered.ToString();

        // Character-level split + id lookup
        var ids = new List<int>();
        foreach (char c in cleanText)
        {
            ids.Add(encoder.TryGetValue(c.ToString(), out int id) ? id : 0);
        }

        // Intersperse blank token (0) between every id
        var interspersed = new List<int> { 0 };
        foreach (var id in ids)
        {
            interspersed.Add(id);
            interspersed.Add(0);
        }

        return interspersed.ToArray();
    }

    // Same pipeline as Encode(), but also returns which real character sits at each
    // position in the interspersed array (empty string "" at every blank position).
    // Needed so the viseme mapper can look up the correct character for each duration value.
    public (int[] ids, string[] chars) EncodeWithCharacters(string text)
    {
        string normalized = NormalizeText(text);
        var filtered = new StringBuilder();
        foreach (char c in normalized)
        {
            if (encoder.ContainsKey(c.ToString()))
                filtered.Append(c);
        }
        string cleanText = filtered.ToString();

        var ids = new List<int>();
        var chars = new List<string>();
        foreach (char c in cleanText)
        {
            ids.Add(encoder.TryGetValue(c.ToString(), out int id) ? id : 0);
            chars.Add(c.ToString());
        }

        var interspersedIds = new List<int> { 0 };
        var interspersedChars = new List<string> { "" };
        for (int i = 0; i < ids.Count; i++)
        {
            interspersedIds.Add(ids[i]);
            interspersedChars.Add(chars[i]);
            interspersedIds.Add(0);
            interspersedChars.Add("");
        }

        return (interspersedIds.ToArray(), interspersedChars.ToArray());
    }
}