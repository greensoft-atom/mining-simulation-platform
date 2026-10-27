using System;

namespace Deepforge.Client.Time
{
    /// <summary>Monotonic seconds since app start. Unity: <c>Time.realtimeSinceStartupAsDouble</c>.
    /// Never the device wall clock: players can change it.</summary>
    public interface IMonotonicClock
    {
        double Seconds { get; }
    }

    /// <summary>
    /// Server-synchronised "now" for every gameplay timer (FR-BOOT-005). Each response's serverTime gives
    /// an offset sample (server − monotonic); the median of the last 5 samples rejects outliers from slow
    /// responses. The result keeps ticking with the monotonic clock between responses.
    /// </summary>
    public sealed class ServerClock
    {
        private const int Window = 5;
        private readonly IMonotonicClock _mono;
        private readonly double[] _samples = new double[Window];
        private readonly double[] _sorted = new double[Window];
        private int _count;
        private int _next;
        private double _offset;

        public ServerClock(IMonotonicClock mono) => _mono = mono;

        public bool IsSynced => _count > 0;

        /// <param name="serverTime">Envelope.ServerTime.</param>
        /// <param name="roundTripSeconds">Request round trip if known; half of it is assumed to be the return leg.</param>
        public void Observe(DateTimeOffset serverTime, double roundTripSeconds = 0)
        {
            double server = serverTime.ToUnixTimeMilliseconds() / 1000.0 + roundTripSeconds / 2;
            _samples[_next] = server - _mono.Seconds;
            _next = (_next + 1) % Window;
            if (_count < Window) _count++;

            Array.Copy(_samples, _sorted, _count);
            Array.Sort(_sorted, 0, _count);
            _offset = _count % 2 == 1
                ? _sorted[_count / 2]
                : (_sorted[_count / 2 - 1] + _sorted[_count / 2]) / 2;
        }

        public DateTimeOffset Now
        {
            get
            {
                if (!IsSynced) throw new InvalidOperationException("ServerClock not synced; call bootstrap first.");
                return DateTimeOffset.FromUnixTimeMilliseconds((long)Math.Round((_mono.Seconds + _offset) * 1000));
            }
        }

        /// <summary>Time left until a server timestamp (production done, run expiry...), never negative.</summary>
        public TimeSpan Until(DateTimeOffset serverInstant)
        {
            var left = serverInstant - Now;
            return left < TimeSpan.Zero ? TimeSpan.Zero : left;
        }
    }
}
