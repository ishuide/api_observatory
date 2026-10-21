import React, { useEffect, useRef } from "react";
import { Network } from "vis-network/standalone";

export default function DependencyGraph({ agents, resources, dependencies }) {
    const containerRef = useRef(null);

    useEffect(() => {
        if (!containerRef.current) return;

        const nodes = [
            ...agents.map(a => ({
                id: `a_${a.agent_id}`,
                label: `${a.name}\n(${a.status})`,
                color: {
                    background: a.status === 'ACTIVE' ? '#1e1b4b' : '#4c0519',
                    border: a.status === 'ACTIVE' ? '#6366f1' : '#f43f5e',
                    highlight: { background: '#312e81', border: '#818cf8' }
                },
                shape: 'box',
                margin: 10,
                font: { color: '#ffffff', face: 'system-ui', size: 12, multi: true },
                borderWidth: 1.5
            })),
            ...resources.map(r => ({
                id: `r_${r.resource_id}`,
                label: `${r.name}\n[${r.resource_type}] - ${r.status}`,
                color: {
                    background: r.status === 'HEALTHY' ? '#064e3b' : '#7f1d1d',
                    border: r.status === 'HEALTHY' ? '#10b981' : '#ef4444',
                    highlight: { background: '#065f46', border: '#34d399' }
                },
                shape: 'ellipse',
                margin: 10,
                font: { color: '#ffffff', face: 'system-ui', size: 11, multi: true },
                borderWidth: 1.5
            }))
        ];

        const edges = dependencies.map(d => ({
            from: `a_${d.agent_id}`,
            to: `r_${d.resource_id}`,
            arrows: { to: { enabled: true, scaleFactor: 0.8 } },
            color: {
                color: d.is_critical ? '#f43f5e' : '#64748b',
                highlight: '#fb7185'
            },
            dashes: !d.is_critical,
            label: d.dependency_type,
            font: { color: '#94a3b8', size: 10, align: 'middle', background: '#020617' },
            width: d.is_critical ? 1.5 : 1
        }));

        const options = {
            layout: {
                improvedLayout: true,
                randomSeed: 17
            },
            physics: {
                enabled: true,
                solver: 'barnesHut',
                barnesHut: {
                    gravitationalConstant: -1800,
                    centralGravity: 0.25,
                    springLength: 150,
                    springConstant: 0.025,
                    damping: 0.65,
                    avoidOverlap: 0.25
                },
                stabilization: {
                    enabled: true,
                    iterations: 300,
                    updateInterval: 25,
                    fit: true
                },
                minVelocity: 0.75,
                maxVelocity: 30,
                timestep: 0.35
            },
            interaction: { hover: true, tooltipDelay: 100 },
            height: '520px',
            width: '100%'
        };

        const network = new Network(containerRef.current, { nodes, edges }, options);
        network.once('stabilizationIterationsDone', () => {
            network.setOptions({ physics: { enabled: false } });
        });
        return () => network.destroy();
    }, [agents, resources, dependencies]);

    return <div ref={containerRef} className="w-full h-[520px] bg-slate-950/80 rounded-xl border border-slate-800 shadow-inner" />;
}