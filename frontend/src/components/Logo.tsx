import React, { useState, useEffect } from 'react';

interface LogoProps {
    animatedText?: boolean;
    sequence?: string[];
    speed?: number;
    delay?: number;
    loop?: boolean;
}

const Logo: React.FC<LogoProps> = ({
    animatedText = false,
    sequence = ["ThoughtOS"],
    speed = 100,
    delay = 2000,
    loop = false
}) => {
    const [displayText, setDisplayText] = useState('');
    const [index, setIndex] = useState(0);
    const [subIndex, setSubIndex] = useState(0);
    const [isDeleting, setIsDeleting] = useState(false);
    const [cursorVisible, setCursorVisible] = useState(true);

    // Cursor blinking effect
    useEffect(() => {
        if (!animatedText) return;
        const cursorInterval = setInterval(() => {
            setCursorVisible(v => !v);
        }, 500);
        return () => clearInterval(cursorInterval);
    }, [animatedText]);

    // Typing effect
    useEffect(() => {
        if (!animatedText || sequence.length === 0) return;

        const handleTyping = () => {
            const currentString = sequence[index];

            if (isDeleting) {
                setDisplayText(currentString.substring(0, subIndex - 1));
                setSubIndex(prev => prev - 1);
            } else {
                setDisplayText(currentString.substring(0, subIndex + 1));
                setSubIndex(prev => prev + 1);
            }

            // Determine next state
            if (!isDeleting && subIndex === currentString.length) {
                // Finished typing current string
                if (index === sequence.length - 1 && !loop) {
                    // Stop if it's the last string and no loop
                    return;
                }
                // Pause before deleting
                setTimeout(() => setIsDeleting(true), delay);
            } else if (isDeleting && subIndex === 0) {
                // Finished deleting
                setIsDeleting(false);
                setIndex(prev => (prev + 1) % sequence.length);
            }
        };

        const timeout = setTimeout(handleTyping, isDeleting ? speed / 2 : speed);
        return () => clearTimeout(timeout);
    }, [animatedText, subIndex, isDeleting, index, sequence, speed, delay, loop]);

    if (animatedText) {
        return (
            <div style={{
                fontFamily: "'Courier Prime', 'Courier New', monospace",
                fontSize: '24px',
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                color: 'black',
                whiteSpace: 'nowrap'
            }}>
                <span>[</span>
                <span style={{ margin: '0 8px' }}>
                    {displayText}
                    <span style={{
                        display: 'inline-block',
                        width: '0.6em',
                        height: '1em',
                        backgroundColor: 'black',
                        marginLeft: '2px',
                        verticalAlign: '-0.15em',
                        opacity: cursorVisible ? 1 : 0,
                        transition: 'opacity 0.1s'
                    }}></span>
                </span>
                <span>]</span>
            </div>
        );
    }

    return (
        <svg
            width="32"
            height="32"
            viewBox="0 0 32 32"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: 'block' }}
        >
            <style>
                {`
                    @keyframes blink {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0; }
                    }
                    .cursor {
                        animation: blink 1s step-end infinite;
                    }
                `}
            </style>

            {/* Left Bracket [ */}
            <path
                d="M10 8H6V24H10"
                stroke="black"
                strokeWidth="4"
                strokeLinecap="square"
            />

            {/* Right Bracket ] */}
            <path
                d="M22 8H26V24H22"
                stroke="black"
                strokeWidth="4"
                strokeLinecap="square"
            />

            {/* Center Block (Cursor) */}
            <rect
                x="13"
                y="11"
                width="6"
                height="10"
                fill="black"
                className="cursor"
            />
        </svg>
    );
};

export default Logo;
