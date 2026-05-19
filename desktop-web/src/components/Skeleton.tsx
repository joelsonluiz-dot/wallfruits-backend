import React from 'react';
import './skeleton.css';

export default function Skeleton({lines = 3}:{lines?:number}){
  return (
    <div className="wf-skeleton">
      {Array.from({length: lines}).map((_,i)=> (
        <div key={i} className="wf-skeleton-line" />
      ))}
    </div>
  );
}
