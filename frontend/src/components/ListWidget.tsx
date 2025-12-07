import React from 'react';

interface Transaction {
    date: string;
    merchant: string;
    amount: number;
}

interface ListWidgetProps {
    data: {
        transactions: Transaction[];
    };
}

const ListWidget: React.FC<ListWidgetProps> = ({ data }) => {
    return (
        <div style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #eee',
            marginTop: '12px',
            overflow: 'hidden',
            width: '100%',
            maxWidth: '500px'
        }}>
            {data.transactions.map((txn, i) => (
                <div key={i} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    borderBottom: i < data.transactions.length - 1 ? '1px solid #f5f5f5' : 'none'
                }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontWeight: '500', fontSize: '14px' }}>{txn.merchant}</span>
                        <span style={{ fontSize: '12px', color: '#999' }}>{txn.date}</span>
                    </div>
                    <span style={{
                        fontWeight: '600',
                        fontSize: '14px',
                        color: txn.amount > 0 ? 'black' : '#34C759' // Green for credits
                    }}>
                        ${Math.abs(txn.amount).toFixed(2)}
                    </span>
                </div>
            ))}
        </div>
    );
};

export default ListWidget;
