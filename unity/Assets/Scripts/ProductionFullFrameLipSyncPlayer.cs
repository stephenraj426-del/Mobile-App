using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;

[Serializable]
public class ProductionLipSyncFrame
{
    public float time;
    public float end;
    public string unit;
    public string viseme;
    public int spriteIndex;
    public float jawOpen;
    public float mouthScaleX = 1f;
    public float mouthScaleY = 1f;
    public float confidence = 1f;
}

[Serializable]
public class ProductionLipSyncClip
{
    public string version;
    public string source;
    public string language;
    public string audioFile;
    public float duration;
    public string rawText;
    public string normalizedText;
    public string spriteProfile;
    public ProductionLipSyncFrame[] frames;
}

[Serializable]
public class VisemeFrameSet
{
    [Tooltip("The 5 FRAME_<NAME>_0..4.png sprites for this viseme, in order.")]
    public Sprite[] frames = new Sprite[5];
}

/// <summary>
/// Production 21-sprite lip-sync player using FULL-FRAME dual-crossfade
/// rendering -- matches art like Unity_FullFrame_Sequences222 (720x1280
/// complete character frames, 21 visemes x 5 frames each), not a small
/// mouth-only overlay.
///
/// Two things happen at once, same as the original FullFrameSequencePlayer:
/// 1. On a VISEME change, the two SpriteRenderers swap which one is "in
///    front" and crossfade between them (smooths the cut between visemes).
/// 2. WITHIN a single viseme's hold duration, the active renderer cycles
///    through that viseme's 5 frames based on progress through the hold --
///    all 5 frames get used, not just the first one.
///
/// Expected StreamingAssets layout:
/// StreamingAssets/LipSync/&lt;jobFolder&gt;/avatar.wav
/// StreamingAssets/LipSync/&lt;jobFolder&gt;/lipsync.json
/// </summary>
public class ProductionFullFrameLipSyncPlayer : MonoBehaviour
{
    [Header("Input")]
    [Tooltip("Example: LipSync/en_test_001")]
    public string streamingAssetsJobFolder = "LipSync/en_test_001";

    [Header("Dual-Layer Rendering")]
    public AudioSource audioSource;
    public SpriteRenderer primaryRenderer;
    public SpriteRenderer secondaryRenderer;
    [Tooltip("21 entries (index 0-20, see README for order), each with its 5 sub-frames.")]
    public VisemeFrameSet[] visemeFrameSets = new VisemeFrameSet[21];

    [Header("Playback")]
    public bool playOnStart = true;
    public bool loop = false;
    public float globalTimeOffsetSeconds = 0f;

    [Header("Sub-Frame Cycling")]
    [Tooltip("How long each of a viseme's 5 sub-frames is shown for, in seconds, before advancing to the next. Matches how far apart the source video frames actually were (1/24fps source = ~0.0417) so motion plays at its natural speed instead of racing through all 5 frames within short viseme holds. Raise this if mouth movement still looks too fast; lower it if it looks too slow/sluggish.")]
    public float subFrameDurationSeconds = 0.0417f;

    [Header("Crossfade")]
    [Tooltip("Higher values (35-45) give a snappier, less blurred transition between visemes.")]
    public float crossFadeSpeed = 38f;

    [Header("Debug")]
    public bool logFrames = false;
    public int currentFrameIndex = -1;
    public string currentViseme = "";
    public string currentUnit = "";

    private ProductionLipSyncClip clipData;
    private int cursor;
    private int lastSpriteIndex = -999;
    private bool isTargetingPrimary = true;
    private float layerCrossBlend = 1f;
    private bool isReady;

    private void Reset()
    {
        audioSource = GetComponent<AudioSource>();
    }

    private IEnumerator Start()
    {
        if (audioSource == null)
            audioSource = GetComponent<AudioSource>();

        if (primaryRenderer != null && secondaryRenderer != null)
        {
            primaryRenderer.sortingOrder = 10;
            secondaryRenderer.sortingOrder = 9;
        }

        yield return LoadFromStreamingAssets();

        if (playOnStart && isReady)
            Play();
    }

    public void Play()
    {
        if (!isReady || audioSource == null || audioSource.clip == null)
        {
            Debug.LogError("ProductionFullFrameLipSyncPlayer is not ready. Check AudioSource, WAV, JSON, and sprites.");
            return;
        }

        cursor = 0;
        currentFrameIndex = -1;
        lastSpriteIndex = -999;
        isTargetingPrimary = true;
        layerCrossBlend = 1f;
        audioSource.loop = loop;
        audioSource.time = 0f;
        audioSource.Play();
        ApplyRestFrame();
    }

    public void Stop()
    {
        if (audioSource != null)
            audioSource.Stop();
        ApplyRestFrame();
    }

    private void Update()
    {
        if (!isReady || audioSource == null || clipData == null || clipData.frames == null)
            return;

        if (audioSource.isPlaying)
        {
            float t = GetAccurateAudioTime() + globalTimeOffsetSeconds;
            ApplyFrameForTime(t);
        }

        ExecuteLayerCrossfade();
    }

    private float GetAccurateAudioTime()
    {
        if (audioSource.clip == null || audioSource.clip.frequency <= 0)
            return audioSource.time;
        return (float)audioSource.timeSamples / audioSource.clip.frequency;
    }

    // Frames from the backend are guaranteed non-overlapping and contiguous
    // (smoothing.py enforces this), so a monotonic forward cursor is safe --
    // it never needs to jump backward or re-scan from zero.
    private void ApplyFrameForTime(float t)
    {
        ProductionLipSyncFrame[] frames = clipData.frames;
        if (frames.Length == 0)
            return;

        while (cursor < frames.Length - 1 && t >= frames[cursor].end)
            cursor++;

        ProductionLipSyncFrame frame = frames[cursor];
        if (t < frame.time && cursor > 0)
            frame = frames[cursor - 1];

        currentFrameIndex = cursor;
        currentViseme = frame.viseme;
        currentUnit = frame.unit;

        int safeIndex = Mathf.Clamp(frame.spriteIndex, 0, visemeFrameSets.Length - 1);
        Sprite[] subFrames = visemeFrameSets[safeIndex]?.frames;
        if (subFrames == null || subFrames.Length == 0)
            return;

        // Cycle through this viseme's 5 frames at a fixed real-time rate,
        // not stretched/compressed to fit the hold's duration. The 5 frames
        // were extracted from 5 consecutive source-video frames (~42ms
        // apart), capturing ~167ms of real motion. The old code used
        // progress-through-hold (elapsed/segDuration * 5), which forces ALL
        // 5 frames to play out even when a viseme is only held 55-80ms --
        // squeezing 167ms of real motion into a fraction of that time, i.e.
        // playing it back 2-3x faster than it naturally moved. Confirmed
        // with real data: most viseme holds in actual sentences are
        // 55-150ms, well under the 167ms the frames actually span.
        float segDuration = Mathf.Max(0.001f, frame.end - frame.time);
        float elapsed = t - frame.time;
        int subIndex = Mathf.Clamp(Mathf.FloorToInt(elapsed / subFrameDurationSeconds), 0, subFrames.Length - 1);
        Sprite activeSprite = subFrames[subIndex];
        if (activeSprite == null)
            return;

        bool visemeChanged = safeIndex != lastSpriteIndex;
        if (visemeChanged)
        {
            isTargetingPrimary = !isTargetingPrimary;
            lastSpriteIndex = safeIndex;
            if (logFrames)
                Debug.Log($"LipSync t={t:F3} unit={frame.unit} viseme={frame.viseme} sprite={safeIndex} subFrame={subIndex}");
        }

        if (isTargetingPrimary)
        {
            if (visemeChanged)
            {
                primaryRenderer.sortingOrder = 9;
                secondaryRenderer.sortingOrder = 10;
                SetAlpha(primaryRenderer, 1f);
            }
            primaryRenderer.sprite = activeSprite;
        }
        else
        {
            if (visemeChanged)
            {
                secondaryRenderer.sortingOrder = 9;
                primaryRenderer.sortingOrder = 10;
                SetAlpha(secondaryRenderer, 1f);
            }
            secondaryRenderer.sprite = activeSprite;
        }
    }

    private void ExecuteLayerCrossfade()
    {
        if (primaryRenderer == null || secondaryRenderer == null)
            return;

        if (isTargetingPrimary)
        {
            layerCrossBlend = Mathf.MoveTowards(layerCrossBlend, 1f, Time.deltaTime * crossFadeSpeed);
            SetAlpha(secondaryRenderer, 1f - layerCrossBlend);
            SetAlpha(primaryRenderer, 1f);
        }
        else
        {
            layerCrossBlend = Mathf.MoveTowards(layerCrossBlend, 0f, Time.deltaTime * crossFadeSpeed);
            SetAlpha(primaryRenderer, layerCrossBlend);
            SetAlpha(secondaryRenderer, 1f);
        }
    }

    private static void SetAlpha(SpriteRenderer renderer, float alpha)
    {
        Color c = renderer.color;
        c.a = alpha;
        renderer.color = c;
    }

    private void ApplyRestFrame()
    {
        Sprite[] restFrames = (visemeFrameSets != null && visemeFrameSets.Length > 0) ? visemeFrameSets[0]?.frames : null;
        if (restFrames == null || restFrames.Length == 0)
            return;

        // Middle frame of the rest sequence, not frame 0 -- avoids always
        // resting on the exact same static pose.
        Sprite restSprite = restFrames[restFrames.Length / 2];
        if (restSprite == null)
            restSprite = restFrames[0];
        if (restSprite == null)
            return;

        if (primaryRenderer != null)
        {
            primaryRenderer.sprite = restSprite;
            primaryRenderer.color = Color.white;
            primaryRenderer.sortingOrder = 10;
        }
        if (secondaryRenderer != null)
        {
            secondaryRenderer.sprite = restSprite;
            secondaryRenderer.color = new Color(1f, 1f, 1f, 0f);
            secondaryRenderer.sortingOrder = 9;
        }

        isTargetingPrimary = true;
        layerCrossBlend = 1f;
        lastSpriteIndex = 0;
    }

    private IEnumerator LoadFromStreamingAssets()
    {
        string folder = Path.Combine(Application.streamingAssetsPath, streamingAssetsJobFolder);
        string jsonPath = Path.Combine(folder, "lipsync.json");

        string jsonText = null;
        yield return LoadText(jsonPath, text => jsonText = text);
        if (string.IsNullOrWhiteSpace(jsonText))
        {
            Debug.LogError($"Could not load lipsync JSON: {jsonPath}");
            yield break;
        }

        clipData = JsonUtility.FromJson<ProductionLipSyncClip>(jsonText);
        if (clipData == null || clipData.frames == null || clipData.frames.Length == 0)
        {
            Debug.LogError("LipSync JSON loaded, but frames are empty.");
            yield break;
        }

        string audioFile = string.IsNullOrWhiteSpace(clipData.audioFile) ? "avatar.wav" : clipData.audioFile;
        string audioPath = Path.Combine(folder, audioFile);
        AudioClip loadedClip = null;
        yield return LoadWav(audioPath, c => loadedClip = c);
        if (loadedClip == null)
        {
            Debug.LogError($"Could not load WAV audio: {audioPath}");
            yield break;
        }

        audioSource.clip = loadedClip;
        ValidateSetup();
        ApplyRestFrame();
        isReady = true;
        Debug.Log($"LipSync ready: {streamingAssetsJobFolder}, frames={clipData.frames.Length}, duration={clipData.duration:F2}s");
    }

    private void ValidateSetup()
    {
        if (audioSource == null)
            throw new Exception("AudioSource is missing.");
        if (primaryRenderer == null || secondaryRenderer == null)
            throw new Exception("Primary/Secondary SpriteRenderer is missing.");
        if (visemeFrameSets == null || visemeFrameSets.Length < 21)
            throw new Exception("Assign exactly 21 viseme frame sets in the expected order.");

        for (int i = 0; i < 21; i++)
        {
            var set = visemeFrameSets[i];
            if (set == null || set.frames == null || set.frames.Length == 0)
            {
                Debug.LogWarning($"Viseme frame set index {i} has no sprites assigned.");
                continue;
            }
            for (int f = 0; f < set.frames.Length; f++)
            {
                if (set.frames[f] == null)
                    Debug.LogWarning($"Viseme {i}, sub-frame {f} is not assigned.");
            }
        }
    }

    private IEnumerator LoadText(string path, Action<string> done)
    {
        string uri = ToUri(path);
        using (UnityWebRequest req = UnityWebRequest.Get(uri))
        {
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError(req.error);
                done(null);
            }
            else
            {
                done(req.downloadHandler.text);
            }
        }
    }

    private IEnumerator LoadWav(string path, Action<AudioClip> done)
    {
        string uri = ToUri(path);
        using (UnityWebRequest req = UnityWebRequestMultimedia.GetAudioClip(uri, AudioType.WAV))
        {
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError(req.error);
                done(null);
            }
            else
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(req);
                done(clip);
            }
        }
    }

    private string ToUri(string path)
    {
        if (path.Contains("://"))
            return path;
        return "file:///" + path.Replace("\\", "/");
    }
}
