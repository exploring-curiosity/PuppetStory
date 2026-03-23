import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import CatalogPage from './pages/CatalogPage';
import LoadingPage from './pages/LoadingPage';
import PlaybackPage from './pages/PlaybackPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CatalogPage />} />
        <Route path="/loading/:storyId" element={<LoadingPage />} />
        <Route path="/play/:storyId" element={<PlaybackPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
