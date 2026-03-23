import { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchStory, generateAssets, type StoryData, type AssetGenEvent } from '../lib/api';
import { Loader2, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';

interface ProgressItem {
  id: string;
  status: 'pending' | 'generating' | 'done' | 'error';
  type?: string;
}

export default function LoadingPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const [story, setStory] = useState<StoryData | null>(null);
  const [items, setItems] = useState<ProgressItem[]>([]);
  const [done, setDone] = useState(0);
  const [total, setTotal] = useState(0);
  const [phase, setPhase] = useState<'loading' | 'generating' | 'complete' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const startedRef = useRef(false);

  useEffect(() => {
    if (!storyId || startedRef.current) return;
    startedRef.current = true;

    (async () => {
      try {
        const storyData = await fetchStory(storyId);
        setStory(storyData);

        // Build progress items list
        const progressItems: ProgressItem[] = [];
        if (storyData.cover_prompt) {
          progressItems.push({ id: '_cover', status: 'pending', type: 'cover' });
        }
        for (const c of storyData.characters) {
          progressItems.push({ id: c.id, status: 'pending', type: 'character' });
        }
        for (const b of storyData.backgrounds) {
          progressItems.push({ id: b.id, status: 'pending', type: 'background' });
        }
        setItems(progressItems);
        setTotal(progressItems.length);
        setPhase('generating');

        await generateAssets(storyId, (event: AssetGenEvent) => {
          if (event.event === 'start') {
            setTotal(event.total || 0);
          } else if (event.event === 'progress' || event.event === 'cached') {
            setDone(event.done || 0);
            if (event.current) {
              setItems(prev => prev.map(item =>
                item.id === event.current ? { ...item, status: 'done' } : item
              ));
            }
          } else if (event.event === 'error') {
            setDone(event.done || 0);
            if (event.element) {
              setItems(prev => prev.map(item =>
                item.id === event.element ? { ...item, status: 'error' } : item
              ));
            }
          } else if (event.event === 'complete') {
            setPhase('complete');
          }
        });

        setPhase('complete');
      } catch (e: any) {
        setErrorMsg(e.message || 'Unknown error');
        setPhase('error');
      }
    })();
  }, [storyId]);

  const progress = total > 0 ? Math.round((done / total) * 100) : 0;

  const handleStart = () => {
    navigate(`/play/${storyId}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a1a] to-[#1a1a2e] flex flex-col items-center justify-center px-6">
      <div className="max-w-lg w-full">
        {/* Title */}
        <div className="text-center mb-10">
          <Sparkles className="w-8 h-8 text-amber-400 mx-auto mb-3" />
          <h1 className="text-3xl font-bold text-white mb-2">
            {story ? story.title : 'Loading...'}
          </h1>
          <p className="text-slate-400 text-sm">
            {phase === 'loading' && 'Fetching story data...'}
            {phase === 'generating' && 'Generating puppet images and backgrounds...'}
            {phase === 'complete' && 'All assets ready! Let the story begin.'}
            {phase === 'error' && 'Something went wrong.'}
          </p>
        </div>

        {/* Progress bar */}
        {(phase === 'generating' || phase === 'complete') && (
          <div className="mb-8">
            <div className="flex justify-between text-xs text-slate-500 mb-2">
              <span>{done} / {total} assets</span>
              <span>{progress}%</span>
            </div>
            <div className="h-3 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-500 to-amber-500 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Item list */}
        {items.length > 0 && (
          <div className="space-y-2 mb-10 max-h-64 overflow-y-auto pr-2">
            {items.map((item) => (
              <div
                key={item.id}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all ${
                  item.status === 'done'
                    ? 'bg-emerald-500/10 text-emerald-300'
                    : item.status === 'error'
                    ? 'bg-red-500/10 text-red-300'
                    : item.status === 'generating'
                    ? 'bg-violet-500/10 text-violet-300'
                    : 'bg-white/5 text-slate-500'
                }`}
              >
                {item.status === 'done' && <CheckCircle2 className="w-4 h-4 shrink-0" />}
                {item.status === 'error' && <AlertCircle className="w-4 h-4 shrink-0" />}
                {item.status === 'generating' && <Loader2 className="w-4 h-4 shrink-0 animate-spin" />}
                {item.status === 'pending' && <div className="w-4 h-4 shrink-0 rounded-full border border-slate-600" />}
                <span className="truncate">{item.id.replace(/_/g, ' ')}</span>
                <span className="ml-auto text-xs opacity-50">{item.type}</span>
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {phase === 'error' && (
          <div className="text-center mb-8">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <p className="text-red-300 text-sm mb-4">{errorMsg}</p>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-2.5 bg-white/10 hover:bg-white/15 text-white rounded-lg transition-colors"
            >
              Back to Stories
            </button>
          </div>
        )}

        {/* Actions */}
        {phase === 'complete' && (
          <div className="flex flex-col items-center gap-4">
            <button
              onClick={handleStart}
              className="px-10 py-4 bg-gradient-to-r from-violet-600 to-amber-600 hover:from-violet-500 hover:to-amber-500 text-white font-semibold text-lg rounded-2xl transition-all shadow-lg shadow-violet-900/30 hover:shadow-violet-900/50 hover:-translate-y-0.5"
            >
              Start the Story
            </button>
            <button
              onClick={() => navigate('/')}
              className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Choose a different story
            </button>
          </div>
        )}

        {/* Loading spinner for initial load */}
        {phase === 'loading' && (
          <div className="flex justify-center">
            <Loader2 className="w-10 h-10 text-violet-500 animate-spin" />
          </div>
        )}
      </div>
    </div>
  );
}
