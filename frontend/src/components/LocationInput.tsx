'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface LocationResult {
  display_name: string;
  lat: string;
  lon: string;
  name?: string;
  type?: string;
}

interface LocationInputProps {
  label: string;
  placeholder?: string;
  value: { name: string; lat: number; lng: number } | null;
  onChange: (location: { name: string; lat: number; lng: number }) => void;
  icon?: string;
}

export default function LocationInput({ label, placeholder, value, onChange, icon = '📍' }: LocationInputProps) {
  const [query, setQuery] = useState(value?.name || '');
  const [results, setResults] = useState<LocationResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Sync with external value changes
  useEffect(() => {
    if (value?.name && value.name !== query) {
      setQuery(value.name);
    }
  }, [value?.name]);

  const searchNominatim = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 3) {
      setResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=5&addressdetails=0`,
        {
          headers: { 'Accept-Language': 'en' },
        }
      );
      const data: LocationResult[] = await res.json();
      setResults(data);
      setShowDropdown(data.length > 0);
    } catch (err) {
      console.error('Nominatim search error:', err);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);

    // Debounce search at 500ms
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      searchNominatim(val);
    }, 500);
  };

  const handleSelect = (result: LocationResult) => {
    const shortName = result.display_name.split(',').slice(0, 3).join(',').trim();
    setQuery(shortName);
    setShowDropdown(false);
    setResults([]);
    onChange({
      name: shortName,
      lat: parseFloat(result.lat),
      lng: parseFloat(result.lon),
    });
  };

  return (
    <div ref={wrapperRef} style={{ position: 'relative', flex: 1 }}>
      <label style={{ display: 'block', fontSize: 10, fontWeight: 600, marginBottom: 4, color: 'var(--earth-brown)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {icon} {label}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          className="jm-input"
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          placeholder={placeholder || `Search ${label.toLowerCase()}...`}
          style={{ paddingRight: 32, fontSize: 13, padding: '8px 12px' }}
        />
        {isSearching && (
          <span style={{
            position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 14, animation: 'spin 1s linear infinite',
          }}>
            ⏳
          </span>
        )}
        {value && !isSearching && (
          <span style={{
            position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, color: 'var(--olive-green)',
          }}>
            ✓
          </span>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          background: 'white', border: '1px solid var(--border-green)',
          borderRadius: '0 0 8px 8px', boxShadow: 'var(--shadow-lg)',
          zIndex: 1000, maxHeight: 200, overflowY: 'auto',
        }}>
          {results.map((r, i) => (
            <div
              key={i}
              onClick={() => handleSelect(r)}
              style={{
                padding: '10px 12px', fontSize: 12, cursor: 'pointer',
                borderBottom: i < results.length - 1 ? '1px solid var(--light-sage)' : 'none',
                transition: 'background 0.15s ease',
                color: 'var(--forest-green)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--light-sage)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
            >
              <div style={{ fontWeight: 500 }}>
                {r.display_name.split(',').slice(0, 2).join(', ')}
              </div>
              <div style={{ fontSize: 10, color: 'var(--warm-gray)', marginTop: 2 }}>
                {r.display_name}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
