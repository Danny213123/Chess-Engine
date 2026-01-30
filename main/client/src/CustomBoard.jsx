import React, { useState } from 'react';
import './CustomBoard.css';

const PIECE_IMAGES = {
    'wP': 'https://upload.wikimedia.org/wikipedia/commons/4/45/Chess_plt45.svg',
    'wR': 'https://upload.wikimedia.org/wikipedia/commons/7/72/Chess_rlt45.svg',
    'wN': 'https://upload.wikimedia.org/wikipedia/commons/7/70/Chess_nlt45.svg',
    'wB': 'https://upload.wikimedia.org/wikipedia/commons/b/b1/Chess_blt45.svg',
    'wQ': 'https://upload.wikimedia.org/wikipedia/commons/1/15/Chess_qlt45.svg',
    'wK': 'https://upload.wikimedia.org/wikipedia/commons/4/42/Chess_klt45.svg',
    'bP': 'https://upload.wikimedia.org/wikipedia/commons/c/c7/Chess_pdt45.svg',
    'bR': 'https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg',
    'bN': 'https://upload.wikimedia.org/wikipedia/commons/e/ef/Chess_ndt45.svg',
    'bB': 'https://upload.wikimedia.org/wikipedia/commons/9/98/Chess_bdt45.svg',
    'bQ': 'https://upload.wikimedia.org/wikipedia/commons/4/47/Chess_qdt45.svg',
    'bK': 'https://upload.wikimedia.org/wikipedia/commons/f/f0/Chess_kdt45.svg',
};

// Helper: Parse FEN to 8x8 grid
function parseFen(fen) {
    const board = [];
    const rows = fen.split(' ')[0].split('/');

    for (let r = 0; r < 8; r++) {
        const row = [];
        if (rows[r]) {
            for (let char of rows[r]) {
                if (!isNaN(char)) {
                    for (let i = 0; i < parseInt(char); i++) row.push(null);
                } else {
                    const color = char === char.toUpperCase() ? 'w' : 'b';
                    row.push(color + char.toUpperCase());
                }
            }
        }
        // Fill remaining if malformed
        while (row.length < 8) row.push(null);
        board.push(row);
    }
    return board;
}

const CustomBoard = ({ fen, onMove, orientation = 'white', log, hints = [] }) => {
    const [selectedSq, setSelectedSq] = useState(null);
    const board = parseFen(fen);

    const getSquareName = (r, c) => {
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const rank = 8 - r;
        return `${files[c]}${rank}`;
    };

    const getCoords = (sq) => {
        if (!sq) return null;
        const file = sq.charCodeAt(0) - 97; // 'a' -> 0
        const rank = parseInt(sq[1]);
        const r = 8 - rank;
        const c = file;

        // Return center percentage
        return {
            x: (c * 12.5) + 6.25,
            y: (r * 12.5) + 6.25
        };
    };

    const handleSquareClick = (r, c) => {
        const sqName = getSquareName(r, c);
        log(`CustomClick: ${sqName}`);

        // If nothing selected, select piece
        if (!selectedSq) {
            const piece = board[r][c];
            if (piece) {
                setSelectedSq(sqName);
                log(`Selected: ${sqName}`);
                if (onMove) onMove(sqName, null, "select"); // Notify selection
            }
            return;
        }

        // If same square selected, deselect
        if (selectedSq === sqName) {
            setSelectedSq(null);
            log("Deselected");
            if (onMove) onMove(null, null, "deselect");
            return;
        }

        // Attempt move
        log(`Attempting Move: ${selectedSq} -> ${sqName}`);
        onMove(selectedSq, sqName, "move");
        setSelectedSq(null);
    };

    // Rendering
    const squares = [];
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            const isDark = (r + c) % 2 === 1;
            const sqName = getSquareName(r, c);
            const piece = board[r][c];
            const isSelected = selectedSq === sqName;

            squares.push(
                <div
                    key={sqName}
                    className={`square ${isDark ? 'dark' : 'light'} ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleSquareClick(r, c)}
                >
                    {piece && <img src={PIECE_IMAGES[piece]} alt={piece} className="piece-img" />}
                </div>
            );
        }
    }

    return (
        <div className="custom-board">
            {squares}

            <svg className="arrow-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
                <defs>
                    <marker id="arrowhead" markerWidth="3" markerHeight="3"
                        refX="2" refY="1.5" orient="auto">
                        <polygon points="0 0, 3 1.5, 0 3" fill="rgba(0, 200, 0, 0.8)" />
                    </marker>
                </defs>
                {hints.map((h, i) => {
                    const start = getCoords(h.start);
                    const end = getCoords(h.end);
                    if (!start || !end) return null;
                    return (
                        <line
                            key={i}
                            x1={start.x} y1={start.y}
                            x2={end.x} y2={end.y}
                            stroke={`rgba(0, 255, 0, ${h.opacity})`}
                            strokeWidth="2"
                            markerEnd="url(#arrowhead)"
                        />
                    );
                })}
            </svg>
        </div>
    );
};

export default CustomBoard;
