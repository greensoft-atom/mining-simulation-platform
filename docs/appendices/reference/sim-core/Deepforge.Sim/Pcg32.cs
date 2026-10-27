namespace Deepforge.Sim
{
    /// <summary>
    /// PCG32 (XSH-RR 64/32), M.E. O'Neill. Deterministic across CPUs, runtimes and IL2CPP
    /// because it uses only unsigned 64-bit integer arithmetic. Never use System.Random
    /// (implementation differs between runtimes) or float math inside the simulation.
    /// </summary>
    public struct Pcg32
    {
        private const ulong Multiplier = 6364136223846793005UL;
        private ulong _state;
        private ulong _inc;

        public Pcg32(ulong seed, ulong sequence)
        {
            _state = 0UL;
            _inc = (sequence << 1) | 1UL;
            NextUInt();
            _state += seed;
            NextUInt();
        }

        public uint NextUInt()
        {
            ulong old = _state;
            _state = unchecked(old * Multiplier + _inc);
            uint xorShifted = (uint)(((old >> 18) ^ old) >> 27);
            int rot = (int)(old >> 59);
            return (xorShifted >> rot) | (xorShifted << ((-rot) & 31));
        }

        /// <summary>Uniform integer in [0, bound) without modulo bias.</summary>
        public int NextInt(int bound)
        {
            if (bound <= 0) throw new System.ArgumentOutOfRangeException(nameof(bound));
            uint b = (uint)bound;
            uint threshold = unchecked(0u - b) % b;
            while (true)
            {
                uint r = NextUInt();
                if (r >= threshold) return (int)(r % b);
            }
        }

        /// <summary>True with probability permille/1000.</summary>
        public bool Chance(int permille) => NextInt(1000) < permille;
    }
}
