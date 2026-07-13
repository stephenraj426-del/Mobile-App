using System.Collections.Generic;

public static class VisemeSmoother
{
    // Merges consecutive short intervals so no viseme displays for less than minHoldSeconds
    public static List<VisemeInterval> ApplyMinimumHold(List<VisemeInterval> raw, float minHoldSeconds = 0.08f)
    {
        if (raw.Count == 0) return raw;
        var result = new List<VisemeInterval>();
        int currentViseme = raw[0].visemeIndex;
        float currentStart = raw[0].startTime;
        float currentEnd = raw[0].endTime;

        for (int i = 1; i < raw.Count; i++)
        {
            if (currentEnd - currentStart < minHoldSeconds)
            {
                currentEnd = raw[i].endTime; // not held long enough yet — absorb the next interval
            }
            else
            {
                result.Add(new VisemeInterval(currentViseme, currentStart, currentEnd));
                currentViseme = raw[i].visemeIndex;
                currentStart = raw[i].startTime;
                currentEnd = raw[i].endTime;
            }
        }
        result.Add(new VisemeInterval(currentViseme, currentStart, currentEnd));
        return result;
    }
}