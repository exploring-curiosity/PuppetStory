import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchStories, type StoryCatalogItem } from '../lib/api';
import { BookOpen, Clock, Users, Sparkles } from 'lucide-react';

const COVER_GRADIENTS = [
  'from-violet-600 to-indigo-800',
  'from-amber-500 to-orange-700',
  'from-emerald-500 to-teal-800',
  'from-rose-500 to-pink-800',
  'from-cyan-500 to-blue-800',
  'from-fuchsia-500 to-purple-800',
];

export default function CatalogPage() {
  const [stories, setStories] = useState<StoryCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStories()
      .then(setStories)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a1a] to-[#1a1a2e] overflow-auto">
      {/* Header */}
      <header className="pt-12 pb-8 text-center px-4">
        <div className="flex items-center justify-center gap-3 mb-4">
          <Sparkles className="w-10 h-10 text-amber-400" />
          <h1 className="text-5xl font-bold bg-gradient-to-r from-violet-400 to-amber-400 bg-clip-text text-transparent">
            Puppet Story
          </h1>
          <Sparkles className="w-10 h-10 text-violet-400" />
        </div>
        <p className="text-lg text-slate-400 max-w-xl mx-auto">
          Choose a story and watch it come alive with animated puppets. 
          Interact with your voice to shape the adventure!
        </p>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-6 pb-16">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span className="ml-4 text-slate-400">Loading stories...</span>
          </div>
        )}

        {error && (
          <div className="text-center py-20">
            <p className="text-red-400 text-lg mb-4">Failed to load stories</p>
            <p className="text-slate-500 text-sm">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && stories.length === 0 && (
          <div className="text-center py-20">
            <BookOpen className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-lg">No stories available yet</p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {stories.map((story, i) => (
            <button
              key={story.id}
              onClick={() => navigate(`/loading/${story.id}`)}
              className="group text-left rounded-2xl overflow-hidden bg-[#1a1a2e] border border-white/5 hover:border-violet-500/30 transition-all duration-300 hover:shadow-xl hover:shadow-violet-900/20 hover:-translate-y-1"
            >
              {/* Cover art placeholder */}
              <div className={`h-48 bg-gradient-to-br ${COVER_GRADIENTS[i % COVER_GRADIENTS.length]} flex items-center justify-center relative overflow-hidden`}>
                <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors" />
                <span className="text-6xl relative z-10">
                  {i === 0 ? '🐷' : i === 1 ? '🐻' : i === 2 ? '🐭' : '🐉'}
                </span>
              </div>

              {/* Info */}
              <div className="p-5">
                <h3 className="text-xl font-semibold text-white group-hover:text-violet-300 transition-colors mb-2">
                  {story.title}
                </h3>
                <p className="text-sm text-slate-400 line-clamp-2 mb-4">
                  {story.synopsis}
                </p>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {story.duration_minutes} min
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="w-3.5 h-3.5" />
                    {story.character_count} characters
                  </span>
                  <span className="flex items-center gap-1">
                    <BookOpen className="w-3.5 h-3.5" />
                    Ages {story.age_range[0]}-{story.age_range[1]}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}
