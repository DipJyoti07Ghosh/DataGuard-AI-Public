import { Link } from 'react-router-dom';

export default function NotFound({ resource = 'Page' }) {
  return (
    <div className="page-container" style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '60vh', padding: '2rem',
    }}>
      <div className="glass-card" style={{
        padding: '3rem', maxWidth: '500px', textAlign: 'center',
      }}>
        <span style={{ fontSize: '3rem', marginBottom: '1rem', display: 'block' }}>🔍</span>
        <h2 style={{ margin: '0 0 0.5rem 0' }}>{resource} Not Found</h2>
        <p className="text-muted" style={{ marginBottom: '1.5rem' }}>
          The {resource.toLowerCase()} you're looking for doesn't exist, or you don't have access to it.
        </p>
        <Link to="/datasets" className="btn btn--primary">
          ← Back to Datasets
        </Link>
      </div>
    </div>
  );
}