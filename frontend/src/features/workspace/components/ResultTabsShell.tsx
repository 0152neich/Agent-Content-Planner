import React from 'react';
import { Tab, Tabs, useTheme } from '@mui/material';
import { BarChart3, BriefcaseBusiness, Facebook } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type ResultTabsShellProps = {
  activeTab: number;
  onChangeTab: (tab: number) => void;
};

export const ResultTabsShell: React.FC<ResultTabsShellProps> = ({ activeTab, onChangeTab }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const isDark = theme.palette.mode === 'dark';
  const tabItems = [
    { id: 0, label: t('workspaceResults.tabs.coreAnalysis'), icon: <BarChart3 size={16} /> },
    { id: 1, label: t('workspaceResults.tabs.linkedinPost'), icon: <BriefcaseBusiness size={16} /> },
    { id: 2, label: t('workspaceResults.tabs.facebookPost'), icon: <Facebook size={16} /> },
  ];

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
