using System.Collections.Generic;

public static class TamilVisemeMapper
{
    // Index matches your original 21-category order:
    // 0=REST_CLOSED, 1=AA_WIDE, 2=EE_NARROW, 3=OO_ROUND, 4=UH_MISC, 5=M_B_P, 6=F_V, 7=TH,
    // 8=L_D_T, 9=SH_CH, 10=K_G, 11=S_Z, 12=I_NEAR_EE, 13=O_HALF_OPEN, 14=AW_VOWEL,
    // 15=N_CONSONANT, 16=UR_VOWEL, 17=W_SOUND, 18=H_BREATH, 19=AE_SHORT, 20=ERR_MODIFIER

    private static readonly Dictionary<string, int> map = new Dictionary<string, int>
    {
        // Independent vowels
        {"அ", 1}, {"ஆ", 1}, {"இ", 12}, {"ஈ", 2}, {"உ", 3}, {"ஊ", 3},
        {"எ", 13}, {"ஏ", 13}, {"ஐ", 1}, {"ஒ", 13}, {"ஓ", 13}, {"ஔ", 14},
        // Vowel signs (matras) — inherit the same category as their vowel
        {"ா", 1}, {"ி", 12}, {"ீ", 2}, {"ு", 3}, {"ூ", 3},
        {"ெ", 13}, {"ே", 13}, {"ை", 1}, {"ொ", 13}, {"ோ", 13}, {"ௌ", 14},
        // Consonants (base form)
        {"க", 10}, {"ங", 10}, {"ச", 9}, {"ஞ", 9}, {"ட", 8}, {"ண", 15},
        {"த", 7}, {"ந", 15}, {"ப", 5}, {"ம", 5}, {"ய", 12}, {"ர", 8},
        {"ல", 8}, {"வ", 6}, {"ழ", 8}, {"ள", 8}, {"ற", 8}, {"ன", 15},
        // Loanword letters (grantha)
        {"ஸ", 11}, {"ஷ", 11}, {"ஜ", 9}, {"ஹ", 18},
        // Virama and punctuation/space — treated as rest, folded into neighbor
        {"்", 0}, {" ", 0}, {",", 0}, {".", 0}, {"?", 0}, {"!", 0},
    };

    public static int GetViseme(string character)
    {
        return map.TryGetValue(character, out int viseme) ? viseme : 4; // fall back to UH_MISC if unmapped
    }
}