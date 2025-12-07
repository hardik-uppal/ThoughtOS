import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ConnectStep from './ConnectStep';
import CalibrationStep from './CalibrationStep';
import FreshStartStep from './FreshStartStep';

interface OnboardingWizardProps {
    onComplete: () => void;
}

const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ onComplete }) => {
    const [step, setStep] = useState(0);

    const nextStep = () => setStep(s => s + 1);

    const handleComplete = async () => {
        try {
            await axios.post('/api/onboarding/complete');
            onComplete();
        } catch (e) {
            console.error("Failed to complete onboarding", e);
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(255, 255, 255, 0.8)',
            backdropFilter: 'blur(10px)',
            zIndex: 2000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
        }}>
            <div style={{
                width: '600px',
                background: 'white',
                borderRadius: '24px',
                padding: '40px',
                boxShadow: '0 20px 60px rgba(0,0,0,0.1)',
                border: '1px solid rgba(0,0,0,0.05)'
            }}>
                {/* Progress Bar */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '32px' }}>
                    {[0, 1, 2].map(i => (
                        <div key={i} style={{
                            flex: 1,
                            height: '4px',
                            borderRadius: '2px',
                            background: i <= step ? '#007AFF' : '#eee',
                            transition: 'all 0.3s ease'
                        }} />
                    ))}
                </div>

                {step === 0 && <ConnectStep onNext={nextStep} />}
                {step === 1 && <CalibrationStep onNext={nextStep} />}
                {step === 2 && <FreshStartStep onComplete={handleComplete} />}
            </div>
        </div>
    );
};

export default OnboardingWizard;
