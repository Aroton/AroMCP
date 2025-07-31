// Valid TSX file for testing
import React, { useState } from 'react';

interface Props {
    title: string;
    onSubmit: (value: string) => void;
}

export const TestComponent: React.FC<Props> = ({ title, onSubmit }) => {
    const [value, setValue] = useState('');
    
    const handleSubmit = () => {
        onSubmit(value);
        setValue('');
    };
    
    return (
        <div className="test-component">
            <h1>{title}</h1>
            <input 
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Enter value"
            />
            <button onClick={handleSubmit}>
                Submit
            </button>
        </div>
    );
};

export default TestComponent;