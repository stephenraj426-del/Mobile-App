using System.Collections;
using System.Diagnostics;
using UnityEngine;
using Unity.InferenceEngine;
using Debug = UnityEngine.Debug;

public class RasaModelFullTest : MonoBehaviour
{
    public ModelAsset modelAsset;
    private Model runtimeModel;
    private Worker worker;
    private AudioSource audioSource;
    private TamilVitsTokenizer tokenizer; // the class you just saved

    void Start()
    {
        runtimeModel = ModelLoader.Load(modelAsset);
        worker = new Worker(runtimeModel, BackendType.CPU);

        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1.0f;

        // --- This is the actual "using it" step ---
        TextAsset vocabAsset = Resources.Load<TextAsset>("vocab");
        tokenizer = new TamilVitsTokenizer(vocabAsset.text);

        // Now generate token IDs live, from real text, instead of a hardcoded array
        int[] shortIds = tokenizer.Encode("வணக்கம்.");
        int[] longIds = tokenizer.Encode("வணக்கம், இன்று உங்களுக்கு எப்படி உதவ முடியும்? நான் இங்கே இருக்கிறேன்.");

        RunInference(shortIds, "WARMUP (discarded)");

        AudioClip shortClip = RunInference(shortIds, "SHORT");
        AudioClip longClip = RunInference(longIds, "LONG");
        StartCoroutine(PlayBothClips(shortClip, longClip));
    }

    AudioClip RunInference(int[] inputIdsArray, string label)
    {
        int len = inputIdsArray.Length;
        int[] attnMaskArray = new int[len];
        for (int i = 0; i < len; i++) attnMaskArray[i] = 1;

        using var inputIdsTensor = new Tensor<int>(new TensorShape(1, len), inputIdsArray);
        using var attnMaskTensor = new Tensor<int>(new TensorShape(1, len), attnMaskArray);
        using var speakerIdTensor = new Tensor<int>(new TensorShape(1), new int[] { 18 });
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
        Debug.Log($"[TIMING] {label}: {sw.ElapsedMilliseconds} ms | {waveformValues.Length} samples | ids: {string.Join(",", inputIdsArray)}");

        var clip = AudioClip.Create(label, waveformValues.Length, 1, 24000, false);
        clip.SetData(waveformValues, 0);
        return clip;
    }

    IEnumerator PlayBothClips(AudioClip shortClip, AudioClip longClip)
    {
        audioSource.clip = shortClip; audioSource.Play();
        yield return new WaitForSeconds(shortClip.length + 1f);
        audioSource.clip = longClip; audioSource.Play();
        yield return new WaitForSeconds(longClip.length + 1f);
    }

    void OnDestroy() => worker?.Dispose();
}