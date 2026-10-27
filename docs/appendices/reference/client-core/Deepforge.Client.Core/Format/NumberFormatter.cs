using System;
using System.Globalization;

namespace Deepforge.Client.Format
{
    /// <summary>
    /// Compact number display (docs/12 §12.12). zh-TW groups by 萬 (10^4) and 億 (10^8); English uses K/M/B.
    /// Values are truncated, never rounded up, so the UI never shows more than the player owns
    /// (12,999 coins shows 1.29萬, not 1.3萬).
    /// </summary>
    public static class NumberFormatter
    {
        public static string Compact(long value, string locale)
        {
            if (value < 0) return "-" + Compact(-value, locale);
            if (value < 10_000) return value.ToString("#,0", CultureInfo.InvariantCulture);
            if (locale != null && locale.StartsWith("zh", StringComparison.OrdinalIgnoreCase))
                return value < 100_000_000L ? Unit(value, 10_000L, 2, "萬") : Unit(value, 100_000_000L, 2, "億");
            if (value < 1_000_000L) return Unit(value, 1_000L, 1, "K");
            if (value < 1_000_000_000L) return Unit(value, 1_000_000L, 1, "M");
            return Unit(value, 1_000_000_000L, 1, "B");
        }

        private static string Unit(long value, long unit, int decimals, string suffix)
        {
            long scale = decimals == 2 ? 100 : 10;
            long scaled = value / (unit / scale);                         // integer truncation
            long whole = scaled / scale, frac = scaled % scale;
            string fracText = decimals == 2 ? frac.ToString("00", CultureInfo.InvariantCulture).TrimEnd('0')
                                            : (frac == 0 ? "" : frac.ToString(CultureInfo.InvariantCulture));
            return whole.ToString("#,0", CultureInfo.InvariantCulture) + (fracText.Length > 0 ? "." + fracText : "") + suffix;
        }

        /// <summary>Durations for timers: "2時15分" / "2h 15m"; seconds shown only under 10 minutes.</summary>
        public static string Duration(TimeSpan t, string locale)
        {
            bool zh = locale != null && locale.StartsWith("zh", StringComparison.OrdinalIgnoreCase);
            if (t < TimeSpan.Zero) t = TimeSpan.Zero;
            int h = (int)t.TotalHours, m = t.Minutes, s = t.Seconds;
            if (h > 0) return zh ? $"{h}時{m:D2}分" : $"{h}h {m:D2}m";
            if (m >= 10) return zh ? $"{m}分" : $"{m}m";
            return zh ? $"{m}分{s:D2}秒" : $"{m}m {s:D2}s";
        }
    }
}
