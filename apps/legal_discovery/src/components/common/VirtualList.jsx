import React, { useRef, useState, useMemo } from 'react';

export default function VirtualList({ items = [], itemHeight = 32, height = 320, renderItem, overscan = 6 }) {
  const [scrollTop, setScrollTop] = useState(0);
  const onScroll = (e) => setScrollTop(e.currentTarget.scrollTop);
  const total = items.length;
  const viewport = Math.max(1, Math.floor(height / itemHeight));
  const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const end = Math.min(total, start + viewport + overscan * 2);
  const topPad = start * itemHeight;
  const visible = useMemo(() => items.slice(start, end), [items, start, end]);
  return (
    <div onScroll={onScroll} style={{ overflowY: 'auto', height: `${height}px` }}>
      <div style={{ height: `${total * itemHeight}px`, position: 'relative' }}>
        <div style={{ position: 'absolute', top: `${topPad}px`, left: 0, right: 0 }}>
          {visible.map((item, i) => (
            <div key={item.id || i} style={{ height: `${itemHeight}px` }}>
              {renderItem(item, start + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

