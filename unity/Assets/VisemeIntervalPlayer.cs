using UnityEngine;
using System.Collections.Generic;

public class VisemeIntervalPlayer : MonoBehaviour
{
    public VisemeFrameSet[] visemeFrameSets; // size 21, populated by the Editor button
    public SpriteRenderer rendererA;
    public SpriteRenderer rendererB;
    public AudioSource audioSource;

    [Tooltip("Real-time seconds per sub-frame — fixes the original 'always plays all 5 regardless of hold length' bug")]
    public float subFrameDuration = 0.04f;
    public float crossfadeDuration = 0.03f;

    private List<VisemeInterval> intervals = new List<VisemeInterval>();
    private int lastVisemeIndex = -1;
    private bool usingA = true;
    private float crossfadeTimer = 0f;

    public void SetTimeline(List<VisemeInterval> newIntervals)
    {
        intervals = newIntervals;
        lastVisemeIndex = -1;
        crossfadeTimer = 0f;
    }

    void Update()
    {
        if (audioSource == null || !audioSource.isPlaying || intervals.Count == 0) return;

        float t = audioSource.time;
        VisemeInterval current = FindCurrentInterval(t);

        float elapsedInInterval = t - current.startTime;
        int subFrame = Mathf.Clamp(
            Mathf.FloorToInt(elapsedInInterval / subFrameDuration),
            0, 4
        );

        UpdateSprite(current.visemeIndex, subFrame);

        if (crossfadeTimer > 0f)
        {
            crossfadeTimer -= Time.deltaTime;
            float alpha = 1f - Mathf.Clamp01(crossfadeTimer / crossfadeDuration);
            SetCrossfadeAlpha(alpha);
        }
    }

    VisemeInterval FindCurrentInterval(float t)
    {
        for (int i = 0; i < intervals.Count; i++)
        {
            if (t >= intervals[i].startTime && t < intervals[i].endTime)
                return intervals[i];
        }
        return intervals[intervals.Count - 1];
    }

    void UpdateSprite(int visemeIndex, int subFrame)
    {
        if (visemeIndex < 0 || visemeIndex >= visemeFrameSets.Length) return;
        Sprite target = visemeFrameSets[visemeIndex].frames[subFrame];

        if (visemeIndex != lastVisemeIndex)
        {
            var incoming = usingA ? rendererB : rendererA;
            incoming.sprite = target;
            crossfadeTimer = crossfadeDuration;
            usingA = !usingA;
            lastVisemeIndex = visemeIndex;
        }
        else
        {
            var active = usingA ? rendererA : rendererB;
            active.sprite = target;
        }
    }

    void SetCrossfadeAlpha(float alpha)
    {
        var incoming = usingA ? rendererA : rendererB;
        var outgoing = usingA ? rendererB : rendererA;
        var c1 = incoming.color; c1.a = alpha; incoming.color = c1;
        var c2 = outgoing.color; c2.a = 1f - alpha; outgoing.color = c2;
    }
}