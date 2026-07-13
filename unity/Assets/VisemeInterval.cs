using UnityEngine;

[System.Serializable]
public class VisemeFrameSet
{
    public Sprite[] frames; // exactly 5 sprites per viseme category
}

public struct VisemeInterval
{
    public int visemeIndex;
    public float startTime;
    public float endTime;

    public VisemeInterval(int visemeIndex, float startTime, float endTime)
    {
        this.visemeIndex = visemeIndex;
        this.startTime = startTime;
        this.endTime = endTime;
    }
}