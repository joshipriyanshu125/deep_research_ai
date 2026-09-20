import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext(null);

export const THEMES = [
  { id: 'cyber', name: 'Cyber Cyan', desc: 'Electric Cyan & Deep Space Blue (Default)', primary: '#00F0FF', accent: '#38BDF8' },
  { id: 'slate', name: 'Midnight Slate', desc: 'Clean Dark Pro for high readability & enterprise', primary: '#38BDF8', accent: '#94A3B8' },
  { id: 'emerald', name: 'Emerald Matrix', desc: 'High-contrast Emerald & Teal terminal aesthetic', primary: '#10B981', accent: '#06B6D4' },
  { id: 'studio', name: 'High Contrast Studio', desc: 'Maximum accessibility & sharpest clarity', primary: '#FACC15', accent: '#FFFFFF' },
];

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    return localStorage.getItem('app-theme') || 'cyber';
  });

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    localStorage.setItem('app-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
