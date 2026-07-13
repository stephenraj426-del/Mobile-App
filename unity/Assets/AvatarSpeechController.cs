using System;
using System.Collections;
using UnityEngine;
using Unity.InferenceEngine;

public class AvatarSpeechController : MonoBehaviour
{
    public ModelAsset modelAsset;
    public VisemeIntervalPlayer visemePlayer;
    private Model runtimeModel;
    private Worker worker;
    private AudioSource audioSource;
    private TamilVitsTokenizer tokenizer;
    private float frameSeconds;

    void Start()
    {
        runtimeModel = ModelLoader.Load(modelAsset);
        worker = new Worker(runtimeModel, BackendType.CPU);

        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1.0f;
        if (visemePlayer != null) visemePlayer.audioSource = audioSource;

        TextAsset vocabAsset = Resources.Load<TextAsset>("vocab");
        tokenizer = new TamilVitsTokenizer(vocabAsset.text);
        frameSeconds = 256f / 24000f;

        Speak("வணக்கம்.", 18, TamilVisemeMapper.GetViseme, warmupOnly: true);
        StartCoroutine(SpeakAllLanguages());
    }

    IEnumerator SpeakAllLanguages()
    {
        Speak("வணக்கம், இன்று உங்களுக்கு எப்படி உதவ முடியும்?", 18, TamilVisemeMapper.GetViseme, warmupOnly: false);
        yield return new WaitForSeconds(audioSource.clip.length + 1f);

        Speak("നമസ്കാരം! ഞാൻ നിങ്ങളുടെ സഹായി ആണ്.", 11, MalayalamVisemeMapper.GetViseme, warmupOnly: false);
        yield return new WaitForSeconds(audioSource.clip.length + 1f);

        Speak("నమస్కారం! నేను మీ సహాయకుడిని.", 19, TeluguVisemeMapper.GetViseme, warmupOnly: false);
        yield return new WaitForSeconds(audioSource.clip.length + 1f);

        Speak("ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸಹಾಯಕ.", 8, KannadaVisemeMapper.GetViseme, warmupOnly: false);
        yield return new WaitForSeconds(audioSource.clip.length + 1f);

        Debug.Log("All four languages spoken.");
    }

    void Speak(string text, int speakerId, Func<string, int> mapper, bool warmupOnly)
    {
        var (ids, chars) = tokenizer.EncodeWithCharacters(text);
        int len = ids.Length;
        int[] attnMaskArray = new int[len];
        for (int i = 0; i < len; i++) attnMaskArray[i] = 1;

        using var inputIdsTensor = new Tensor<int>(new TensorShape(1, len), ids);
        using var attnMaskTensor = new Tensor<int>(new TensorShape(1, len), attnMaskArray);
        using var speakerIdTensor = new Tensor<int>(new TensorShape(1), new int[] { speakerId });
        using var emotionIdTensor = new Tensor<int>(new TensorShape(1), new int[] { 4 });

        worker.SetInput("input_ids", inputIdsTensor);
        worker.SetInput("attention_mask", attnMaskTensor);
        worker.SetInput("speaker_id", speakerIdTensor);
        worker.SetInput("emotion_id", emotionIdTensor);
        worker.Schedule();

        var waveformOutput = worker.PeekOutput("waveform") as Tensor<float>;
        var waveformValues = waveformOutput.DownloadToArray();
        if (warmupOnly) return;

        var durationOutput = worker.PeekOutput("duration") as Tensor<float>;
        var durationValues = durationOutput.DownloadToArray();

        var rawIntervals = DurationToVisemeConverter.Convert(ids, chars, durationValues, frameSeconds, mapper);
        var intervals = VisemeSmoother.ApplyMinimumHold(rawIntervals, 0.08f);
        Debug.Log($"[{text.Substring(0, Math.Min(10, text.Length))}...] Built {rawIntervals.Count} raw intervals, smoothed to {intervals.Count}.");

        var clip = AudioClip.Create("Speech", waveformValues.Length, 1, 24000, false);
        clip.SetData(waveformValues, 0);
        audioSource.clip = clip;

        if (visemePlayer != null) visemePlayer.SetTimeline(intervals);
        audioSource.Play();
    }

    void OnDestroy() => worker?.Dispose();
}