using System;
using System.Collections.Generic;

public static class DurationToVisemeConverter
{
    public static List<VisemeInterval> Convert(int[] tokenIds, string[] tokenChars, float[] durationFrames, float frameSeconds, Func<string, int> visemeMapper)
    {
        int n = durationFrames.Length;
        float[] starts = new float[n];
        float[] ends = new float[n];
        float cumulative = 0f;
        for (int i = 0; i < n; i++)
        {
            starts[i] = cumulative;
            cumulative += durationFrames[i] * frameSeconds;
            ends[i] = cumulative;
        }

        var intervals = new List<VisemeInterval>();
        for (int i = 0; i < n; i++)
        {
            if (tokenIds[i] == 0) continue;

            float spanStart = starts[i];
            if (i > 0 && tokenIds[i - 1] == 0)
                spanStart = starts[i - 1];

            int visemeIndex = visemeMapper(tokenChars[i]);
            intervals.Add(new VisemeInterval(visemeIndex, spanStart, ends[i]));
        }
        return intervals;
    }
}