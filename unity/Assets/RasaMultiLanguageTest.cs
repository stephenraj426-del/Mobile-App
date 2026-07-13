using System.Collections;
using System.Diagnostics;
using UnityEngine;
using Unity.InferenceEngine;
using Debug = UnityEngine.Debug;

public class RasaMultiLanguageTest : MonoBehaviour
{
    public ModelAsset modelAsset;
    private Model runtimeModel;
    private Worker worker;
    private AudioSource audioSource;
    private TamilVitsTokenizer tokenizer;

    void Start()
    {
        runtimeModel = ModelLoader.Load(modelAsset);
        worker = new Worker(runtimeModel, BackendType.CPU);

        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1.0f;

        TextAsset vocabAsset = Resources.Load<TextAsset>("vocab");
        tokenizer = new TamilVitsTokenizer(vocabAsset.text);

        // Warm-up on Tamil, discarded — same as always
        RunInference(tokenizer.Encode("வணக்கம்."), 18, "WARMUP");

        StartCoroutine(TestAllLanguages());
    }

    IEnumerator TestAllLanguages()
    {
        var clipTamil = RunInference(tokenizer.Encode("வணக்கம், இன்று உங்களுக்கு எப்படி உதவ முடியும்?"), 18, "TAMIL");
        audioSource.clip = clipTamil; audioSource.Play();
        yield return new WaitForSeconds(clipTamil.length + 1f);

        var clipMalayalam = RunInference(tokenizer.Encode("നമസ്കാരം! ഞാൻ നിങ്ങളുടെ സഹായി ആണ്."), 11, "MALAYALAM");
        audioSource.clip = clipMalayalam; audioSource.Play();
        yield return new WaitForSeconds(clipMalayalam.length + 1f);

        var clipTelugu = RunInference(tokenizer.Encode("నమస్కారం! నేను మీ సహాయకుడిని."), 19, "TELUGU");
        audioSource.clip = clipTelugu; audioSource.Play();
        yield return new WaitForSeconds(clipTelugu.length + 1f);

        var clipKannada = RunInference(tokenizer.Encode("ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸಹಾಯಕ."), 8, "KANNADA");
        audioSource.clip = clipKannada; audioSource.Play();
        yield return new WaitForSeconds(clipKannada.length + 1f);

        Debug.Log("All four languages tested.");
    }

    AudioClip RunInference(int[] inputIdsArray, int speakerId, string label)
    {
        int len = inputIdsArray.Length;
        int[] attnMaskArray = new int[len];
        for (int i = 0; i < len; i++) attnMaskArray[i] = 1;

        using var inputIdsTensor = new Tensor<int>(new TensorShape(1, len), inputIdsArray);
        using var attnMaskTensor = new Tensor<int>(new TensorShape(1, len), attnMaskArray);
        using var speakerIdTensor = new Tensor<int>(new TensorShape(1), new int[] { speakerId });
        using var emotionIdTensor = new Tensor<int>(new TensorShape(1), new int[] { 4 });

        worker.SetInput("input_ids", inputIdsTensor);
        worker.SetInput("attention_mask", attnMaskTensor);
        worker.SetInput("speaker_id", speakerIdTensor);
        worker.SetInput("emotion_id", emotionIdTensor);

        var sw = Stopwatch.StartNew();
        worker.Schedule();
        var waveformOutput = worker.PeekOutput("waveform") as Tensor<float>;
        var waveformValues = waveformOutput.DownloadToArray();
        sw.Stop();
        Debug.Log($"[TIMING] {label} (speaker {speakerId}): {sw.ElapsedMilliseconds} ms | {waveformValues.Length} samples | ids: {string.Join(",", inputIdsArray)}");

        var clip = AudioClip.Create(label, waveformValues.Length, 1, 24000, false);
        clip.SetData(waveformValues, 0);
        return clip;
    }

    void OnDestroy() => worker?.Dispose();
}