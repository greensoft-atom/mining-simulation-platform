using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Deepforge.Client.Delve
{
    /// <summary>Durable local copy of an in-progress run: config + one byte per accepted local action.</summary>
    public interface IRunLogStore
    {
        void Begin(Guid runId, string configJson);
        void Append(Guid runId, byte action);
        string ReadConfig(Guid runId);
        byte[] ReadActions(Guid runId);
        IReadOnlyList<Guid> ListRuns();
        void Close(Guid runId);
        void Delete(Guid runId);
    }

    /// <summary>
    /// File-backed store under <c>Application.persistentDataPath/runs</c>. Each action is appended and flushed
    /// to the OS immediately, so it survives the app being killed (the common mobile case); it is not fsynced
    /// per tap (that costs milliseconds on cheap storage), so a sudden power loss may drop the last few taps,
    /// which the server treats exactly like an abandoned run.
    /// </summary>
    public sealed class FileRunLogStore : IRunLogStore, IDisposable
    {
        private readonly string _dir;
        private readonly Dictionary<Guid, FileStream> _open = new Dictionary<Guid, FileStream>();

        public FileRunLogStore(string directory)
        {
            _dir = directory;
            Directory.CreateDirectory(_dir);
        }

        private string CfgPath(Guid id) => Path.Combine(_dir, id.ToString("N") + ".cfg");
        private string LogPath(Guid id) => Path.Combine(_dir, id.ToString("N") + ".log");

        public void Begin(Guid runId, string configJson)
        {
            string tmp = CfgPath(runId) + ".tmp";
            File.WriteAllText(tmp, configJson, Encoding.UTF8);
            if (File.Exists(CfgPath(runId))) File.Delete(CfgPath(runId));
            File.Move(tmp, CfgPath(runId));                          // config appears atomically
            File.WriteAllBytes(LogPath(runId), Array.Empty<byte>());
        }

        public void Append(Guid runId, byte action)
        {
            if (!_open.TryGetValue(runId, out var fs))
            {
                fs = new FileStream(LogPath(runId), FileMode.Append, FileAccess.Write, FileShare.Read, 64);
                _open[runId] = fs;
            }
            fs.WriteByte(action);
            fs.Flush();                                              // to the OS: survives process death
        }

        public string ReadConfig(Guid runId) => File.ReadAllText(CfgPath(runId), Encoding.UTF8);

        public byte[] ReadActions(Guid runId)
        {
            Close(runId);
            return File.Exists(LogPath(runId)) ? File.ReadAllBytes(LogPath(runId)) : Array.Empty<byte>();
        }

        public IReadOnlyList<Guid> ListRuns()
        {
            var list = new List<Guid>();
            foreach (var f in Directory.GetFiles(_dir, "*.cfg"))
                if (Guid.TryParseExact(Path.GetFileNameWithoutExtension(f), "N", out var id)) list.Add(id);
            list.Sort();
            return list;
        }

        public void Close(Guid runId)
        {
            if (_open.TryGetValue(runId, out var fs)) { fs.Dispose(); _open.Remove(runId); }
        }

        public void Delete(Guid runId)
        {
            Close(runId);
            if (File.Exists(LogPath(runId))) File.Delete(LogPath(runId));
            if (File.Exists(CfgPath(runId))) File.Delete(CfgPath(runId));
        }

        public void Dispose()
        {
            foreach (var fs in _open.Values) fs.Dispose();
            _open.Clear();
        }
    }
}
