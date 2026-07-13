using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Linq;

[CustomEditor(typeof(VisemeIntervalPlayer))]
public class VisemeFrameAutoPopulator : Editor
{
    private static readonly string[] visemeNames = new string[]
    {
        "REST_CLOSED", "AA_WIDE", "EE_NARROW", "OO_ROUND", "UH_MISC",
        "M_B_P", "F_V", "TH", "L_D_T", "SH_CH", "K_G", "S_Z",
        "I_NEAR_EE", "O_HALF_OPEN", "AW_VOWEL", "N_CONSONANT",
        "UR_VOWEL", "W_SOUND", "H_BREATH", "AE_SHORT", "ERR_MODIFIER"
    };

    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        GUILayout.Space(10);
        if (GUILayout.Button("Auto-Populate Viseme Frames From Folder"))
        {
            string folderPath = EditorUtility.OpenFolderPanel("Select folder containing FRAME_NN_NAME_X sprites", "Assets", "");
            if (!string.IsNullOrEmpty(folderPath))
            {
                PopulateFrames(folderPath);
            }
        }
    }

    private void PopulateFrames(string absoluteFolderPath)
    {
        // --- Explicit check: is this folder actually inside the project's Assets folder? ---
        string dataPath = Application.dataPath.Replace("\\", "/");
        string normalizedFolder = absoluteFolderPath.Replace("\\", "/");

        if (!normalizedFolder.StartsWith(dataPath))
        {
            Debug.LogError(
                $"The folder you selected is NOT inside this Unity project's Assets folder.\n" +
                $"Selected: {normalizedFolder}\n" +
                $"Project Assets folder: {dataPath}\n\n" +
                $"Fix: copy your PNG files into a folder inside Assets (e.g. Assets/VisemeFrames/), " +
                $"then run this button again and select that folder instead."
            );
            return;
        }

        string relativePath = "Assets" + normalizedFolder.Substring(dataPath.Length);

        // --- Check for Texture2D files that AREN'T imported as Sprite ---
        string[] allTextureGuids = AssetDatabase.FindAssets("t:Texture2D", new[] { relativePath });
        string[] spriteGuids = AssetDatabase.FindAssets("t:Sprite", new[] { relativePath });

        if (allTextureGuids.Length > 0 && spriteGuids.Length == 0)
        {
            Debug.LogError(
                $"Found {allTextureGuids.Length} image file(s) in that folder, but none are imported as Sprites.\n\n" +
                $"Fix: select all the PNG files in {relativePath} in the Project window, " +
                $"then in the Inspector set 'Texture Type' to 'Sprite (2D and UI)', click Apply, and run this button again."
            );
            return;
        }

        if (spriteGuids.Length == 0)
        {
            Debug.LogError($"No image files of any kind found in {relativePath}. Double-check this is really the folder containing your FRAME_NN_NAME_X.png files.");
            return;
        }

        var pattern = new Regex(@"FRAME_(\d+)_([A-Z_]+)_(\d+)", RegexOptions.IgnoreCase);
        var collected = new Dictionary<int, Sprite[]>();
        int matchedCount = 0;

        foreach (var guid in spriteGuids)
        {
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            string filename = System.IO.Path.GetFileNameWithoutExtension(assetPath);

            var match = pattern.Match(filename);
            if (!match.Success)
            {
                Debug.LogWarning($"Filename didn't match expected pattern, skipping: {filename}");
                continue;
            }

            string visemeNameInFile = match.Groups[2].Value.ToUpper();
            int subFrame = int.Parse(match.Groups[3].Value);

            int visemeIndex = System.Array.IndexOf(visemeNames, visemeNameInFile);
            if (visemeIndex == -1)
            {
                Debug.LogWarning($"Unknown viseme name in filename, skipping: {filename} (parsed as '{visemeNameInFile}')");
                continue;
            }

            Sprite sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetPath);
            if (sprite == null) continue;

            if (!collected.ContainsKey(visemeIndex))
                collected[visemeIndex] = new Sprite[5];

            if (subFrame < 0 || subFrame > 4)
            {
                Debug.LogWarning($"Sub-frame index out of expected 0-4 range, skipping: {filename}");
                continue;
            }

            collected[visemeIndex][subFrame] = sprite;
            matchedCount++;
        }

        var player = (VisemeIntervalPlayer)target;
        var frameSets = new VisemeFrameSet[21];

        for (int i = 0; i < 21; i++)
        {
            frameSets[i] = new VisemeFrameSet();
            if (collected.ContainsKey(i))
            {
                frameSets[i].frames = collected[i];
                int missing = collected[i].Count(s => s == null);
                if (missing > 0)
                    Debug.LogWarning($"Viseme '{visemeNames[i]}' (index {i}) is missing {missing} of its 5 sub-frames.");
            }
            else
            {
                frameSets[i].frames = new Sprite[5];
                Debug.LogWarning($"No frames found at all for viseme '{visemeNames[i]}' (index {i}).");
            }
        }

        Undo.RecordObject(player, "Auto-Populate Viseme Frames");
        player.visemeFrameSets = frameSets;
        EditorUtility.SetDirty(player);

        Debug.Log($"Auto-populate complete: matched {matchedCount} sprite files across {collected.Count} viseme categories.");
    }
}