import React from 'react';
import { Hero } from '../components/Hero';
import { ContextSimulator } from '../components/ContextSimulator';

export const OverviewPage: React.FC = () => {
  const scrollToSimulator = () => {
    const el = document.getElementById('simulator');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div>
      <Hero onExploreClick={scrollToSimulator} />
      <ContextSimulator />
    </div>
  );
};
