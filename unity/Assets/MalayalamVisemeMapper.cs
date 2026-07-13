using System.Collections.Generic;

public static class MalayalamVisemeMapper
{
    private static readonly Dictionary<string, int> map = new Dictionary<string, int>
    {
        // Independent vowels
        {"അ",1},{"ആ",1},{"ഇ",12},{"ഈ",2},{"ഉ",3},{"ഊ",3},{"ഋ",16},
        {"എ",13},{"ഏ",13},{"ഐ",1},{"ഒ",13},{"ഓ",13},{"ഔ",14},
        // Vowel signs
        {"ാ",1},{"ി",12},{"ീ",2},{"ു",3},{"ൂ",3},{"ൃ",16},
        {"െ",13},{"േ",13},{"ൈ",1},{"ൊ",13},{"ോ",13},{"ൌ",14},
        {"ം",15},{"ഃ",18},
        // Consonants
        {"ക",10},{"ഖ",10},{"ഗ",10},{"ഘ",10},{"ങ",10},
        {"ച",9},{"ഛ",9},{"ജ",9},{"ഝ",9},{"ഞ",9},
        {"ട",8},{"ഠ",8},{"ഡ",8},{"ഢ",8},{"ണ",15},
        {"ത",7},{"ഥ",7},{"ദ",7},{"ധ",7},{"ന",15},
        {"പ",5},{"ഫ",5},{"ബ",5},{"ഭ",5},{"മ",5},
        {"യ",12},{"ര",8},{"ല",8},{"വ",6},
        {"ശ",11},{"ഷ",11},{"സ",11},{"ഹ",18},
        {"ള",8},{"ഴ",8},{"റ",8},
        // Virama, punctuation, space
        {"്",0},{" ",0},{",",0},{".",0},{"?",0},{"!",0},
    };

    public static int GetViseme(string character)
    {
        return map.TryGetValue(character, out int viseme) ? viseme : 4;
    }
}