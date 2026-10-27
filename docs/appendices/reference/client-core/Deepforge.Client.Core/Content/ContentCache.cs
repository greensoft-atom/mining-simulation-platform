using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Deepforge.Client.Content
{
    /// <summary>
    /// Local cache of immutable content bundles (FR-BOOT-002). A bundle is installed only if its SHA-256
    /// matches the hash from bootstrap; the "current" pointer is swapped atomically, and the previous
    /// version is kept, so a failed or corrupt download never leaves the game without valid content.
    /// </summary>
    public sealed class ContentCache
    {
        private const string Pointer = "current.txt";
        private readonly string _dir;
        private readonly int _keep;

        public ContentCache(string directory, int keepVersions = 2)
        {
            _dir = directory;
            _keep = Math.Max(2, keepVersions);
            Directory.CreateDirectory(_dir);
        }

        public string LiveVersion =>
            File.Exists(Path.Combine(_dir, Pointer)) ? File.ReadAllText(Path.Combine(_dir, Pointer), Encoding.UTF8).Trim() : null;

        public bool Has(string version) => File.Exists(BundlePath(version));

        public static string Sha256Hex(byte[] data)
        {
            using (var sha = SHA256.Create())
            {
                var h = sha.ComputeHash(data);
                var sb = new StringBuilder(64);
                foreach (var b in h) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }

        public bool TryInstall(string version, string expectedSha256Hex, byte[] bundle, out string error)
        {
            if (!string.Equals(Sha256Hex(bundle), expectedSha256Hex, StringComparison.OrdinalIgnoreCase))
            {
                error = "hash mismatch";
                return false;
            }
            string tmp = BundlePath(version) + ".tmp";
            File.WriteAllBytes(tmp, bundle);
            if (File.Exists(BundlePath(version))) File.Delete(BundlePath(version));
            File.Move(tmp, BundlePath(version));

            string ptr = Path.Combine(_dir, Pointer), ptrTmp = ptr + ".tmp";
            File.WriteAllText(ptrTmp, version, Encoding.UTF8);
            if (!File.Exists(ptr)) File.Move(ptrTmp, ptr);
            else
            {
                try { File.Replace(ptrTmp, ptr, null); }                   // atomic swap on the same volume
                catch (PlatformNotSupportedException)
                {
                    File.Delete(ptr);                                       // a crash here leaves no pointer:
                    File.Move(ptrTmp, ptr);                                 // boot treats that as "download again"
                }
            }

            Prune(version);
            error = null;
            return true;
        }

        public byte[] LoadLive()
        {
            var v = LiveVersion;
            return v == null ? null : File.ReadAllBytes(BundlePath(v));
        }

        private string BundlePath(string version) => Path.Combine(_dir, "bundle-" + version + ".json.br");

        private void Prune(string live)
        {
            var files = new List<FileInfo>();
            foreach (var f in new DirectoryInfo(_dir).GetFiles("bundle-*.json.br")) files.Add(f);
            files.Sort((a, b) => b.LastWriteTimeUtc.CompareTo(a.LastWriteTimeUtc));
            int kept = 0;
            foreach (var f in files)
            {
                bool isLive = f.Name == "bundle-" + live + ".json.br";
                if (isLive || kept < _keep - 1) { if (!isLive) kept++; continue; }
                f.Delete();
            }
        }
    }
}
