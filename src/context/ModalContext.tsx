import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ModalContextType {
  isQuoteModalOpen: boolean;
  selectedService: string;
  openQuoteModal: (serviceTitle?: string) => void;
  closeQuoteModal: () => void;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export const ModalProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState(false);
  const [selectedService, setSelectedService] = useState('');

  const openQuoteModal = (serviceTitle?: string) => {
    if (serviceTitle) {
      setSelectedService(serviceTitle);
    }
    setIsQuoteModalOpen(true);
  };

  const closeQuoteModal = () => {
    setIsQuoteModalOpen(false);
  };

  return (
    <ModalContext.Provider value={{ isQuoteModalOpen, selectedService, openQuoteModal, closeQuoteModal }}>
      {children}
    </ModalContext.Provider>
  );
};

export const useModal = (): ModalContextType => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
};
