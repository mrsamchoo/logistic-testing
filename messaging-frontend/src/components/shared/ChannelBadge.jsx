const CHANNEL_COLORS = {
  line: 'bg-green-100 text-green-800',
  facebook: 'bg-blue-100 text-blue-800',
  instagram: 'bg-pink-100 text-pink-800',
};

const CHANNEL_LABELS = {
  line: 'LINE',
  facebook: 'Facebook',
  instagram: 'Instagram',
};

export default function ChannelBadge({ type, size = 'sm' }) {
  const sizeClass = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-1';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClass} ${CHANNEL_COLORS[type] || 'bg-gray-100 text-gray-800'}`}>
      {CHANNEL_LABELS[type] || type}
    </span>
  );
}
