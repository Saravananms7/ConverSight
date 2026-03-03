import React, { useState } from 'react';
import { UploadCloud, FileText, CheckCircle, AlertCircle, BarChart3, Settings } from 'lucide-react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('provider', 'deepgram');

    try {
      const resp = await axios.post('/transcribe/audio', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setResult(resp.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "An error occurred during transcription.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <h2>CoverSight</h2>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <a href="#" className="nav-item active" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'white', textDecoration: 'none' }}><BarChart3 size={20} /> Dashboard</a>
          <a href="#" className="nav-item" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'var(--text-secondary)', textDecoration: 'none' }}><FileText size={20} /> History</a>
          <a href="#" className="nav-item" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'var(--text-secondary)', textDecoration: 'none' }}><Settings size={20} /> Settings</a>
        </nav>
      </aside>

      <main className="content">
        <header>
          <h1>Conversational Intelligence</h1>
          <p>Upload a customer support audio file to automatically extract structured insights.</p>
        </header>

        <section className="feature-card">
          <div
            className="file-dropzone"
            style={{ border: '2px dashed var(--border-glass)', borderRadius: '1rem', padding: '3rem', cursor: 'pointer', textAlign: 'center' }}
            onClick={() => document.getElementById('audio-upload').click()}
          >
            <UploadCloud size={48} color="var(--accent)" style={{ marginBottom: '1rem' }} />
            <h3 style={{ marginBottom: '0.5rem' }}>Click or Drag Audio File to Upload</h3>
            <p>Supports MP3, WAV, M4A up to 50MB</p>
            <input
              type="file"
              id="audio-upload"
              accept="audio/*"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
          </div>

          {file && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={20} color="var(--accent)" />
                {file.name}
              </span>
              <button
                onClick={handleUpload}
                disabled={loading}
                style={{ background: 'var(--accent)', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '0.5rem', cursor: loading ? 'not-allowed' : 'pointer' }}
              >
                {loading ? 'Processing...' : 'Analyze Conversation'}
              </button>
            </div>
          )}

          {error && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', color: '#f87171', borderRadius: '0.5rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <AlertCircle size={20} />
              <span>{error}</span>
            </div>
          )}
        </section>

        {result && (
          <section className="feature-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h2>Analysis Results</h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.5rem', borderRadius: '0.75rem' }}>
                <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Summary</h3>
                <p>{result.summary}</p>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.5rem', borderRadius: '0.75rem' }}>
                <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Key Insights</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Sentiment:</span>
                    <strong style={{ color: result.sentiment === 'positive' ? '#10b981' : result.sentiment === 'negative' ? '#ef4444' : '#f8fafc', textTransform: 'capitalize' }}>{result.sentiment}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Language:</span>
                    <strong style={{ textTransform: 'capitalize' }}>{result.detected_language}</strong>
                  </div>
                </div>
              </div>
            </div>

            {result.topics && result.topics.length > 0 && (
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.5rem', borderRadius: '0.75rem' }}>
                <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Detected Topics</h3>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {result.topics.map((topic, i) => (
                    <span key={i} style={{ padding: '0.25rem 0.75rem', background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', borderRadius: '999px', fontSize: '0.875rem' }}>
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.5rem', borderRadius: '0.75rem' }}>
              <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Transcript</h3>
              <div style={{ maxHeight: '200px', overflowY: 'auto', paddingRight: '1rem', color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: '1.6' }}>
                {result.transcript}
              </div>
            </div>

          </section>
        )}
      </main>
    </div>
  );
}

export default App;
