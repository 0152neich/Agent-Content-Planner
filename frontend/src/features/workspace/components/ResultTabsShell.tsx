import React from 'react';
import { Tab, Tabs, useTheme } from '@mui/material';
import { BarChart3, BriefcaseBusiness, Facebook } from 'lucide-react';

type ResultTabsShellProps = {
  activeTab: number;
  onChangeTab: (tab: number) => void;
};

const tabItems = [
  { id: 0, label: 'Core Analysis', icon: <BarChart3 size={16} /> },
  { id: 1, label: 'LinkedIn Post', icon: <BriefcaseBusiness size={16} /> },
  { id: 2, label: 'Facebook Post', icon: <Facebook size={16} /> },
];

export const ResultTabsShell: React.FC<ResultTabsShellProps> = ({ activeTab, onChangeTab }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Tabs
      value={activeTab}
      onChange={(_event, tab) => onChangeTab(tab)}
      variant="scrollable"
      scrollButtons="auto"
      sx={{
        minHeight: 48,
        '& .MuiTabs-indicator': {
          display: 'none',
        },
        '& .MuiTab-root': {
          textTransform: 'none',
          fontWeight: 700,
          minHeight: 38,
          borderRadius: 1.7,
          gap: 0.65,
          px: 1.2,
          py: 0.36,
          color: isDark ? '#9fb2cb' : '#64748b',
          border: '1px solid transparent',
          transition: 'all 0.18s ease',
        },
        '& .MuiTab-root.Mui-selected': {
          color: isDark ? '#f4f8ff' : '#0f172a',
          bgcolor: isDark ? 'rgba(64,99,151,0.34)' : '#eef4ff',
          borderColor: isDark ? 'rgba(106,168,255,0.42)' : '#c6d8ff',
        },
      }}
    >
      {tabItems.map((tab) => (
        <Tab key={tab.id} icon={tab.icon} iconPosition="start" label={tab.label} />
      ))}
    </Tabs>
  );
};
