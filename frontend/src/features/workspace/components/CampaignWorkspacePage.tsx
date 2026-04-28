import React, { useCallback, useState } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import { REFINEMENT_SUGGESTIONS, useCampaignWorkspaceState } from '../hooks/useCampaignWorkspaceState';
import { RefinementSidebar } from './RefinementSidebar';
import { ResultWorkspacePanel } from './ResultWorkspacePanel';
import { ProfileDialog } from '@/features/profile';
import { MiniTaskbar } from './MiniTaskbar';
import { clearAccessToken } from '@/features/auth/authStorage';
import { logoutApi } from '@/features/auth/api/authApi';
import { ProjectSettingsDialog } from '@/features/settings';

export const CampaignWorkspacePage: React.FC = () => {
  const navigate = useNavigate();
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false);
  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);
  const {
    currentUser,
    chatMessages,
    campaignResult,
    activeTab,
    prompt,
    selectedModel,
    modelOptions,
    loadingWorkspace,
    loadingResult,
    refining,
    error,
    showSuggestionChips,
    historyRuns,
    historyLoading,
    historyError,
    restoringRunId,
    setPrompt,
    setSelectedModel,
    setActiveTab,
    sendRefinement,
    cancelRefinement,
    restoreFromRun,
    publishSocialPost,
    getFacebookPages,
  } = useCampaignWorkspaceState();

  const submitPrompt = useCallback(() => {
    void sendRefinement();
  }, [sendRefinement]);

  const submitSuggestion = useCallback(
    (value: string) => {
      void sendRefinement(value);
    },
    [sendRefinement],
  );

  const handleLogout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // no-op
    } finally {
      clearAccessToken();
      setConfirmLogoutOpen(false);
      navigate({ to: '/login' });
    }
  }, [navigate]);

  return (
    <Box
      sx={{
        width: '100vw',
        height: '100dvh',
        minHeight: '100dvh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '56px minmax(300px, 30%) 1fr' },
        gridTemplateRows: { xs: '1fr 1fr', md: '1fr' },
        bgcolor: 'background.default',
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          display: { xs: 'none', md: 'block' },
          minHeight: 0,
          borderRight: '1px solid #d7e2ef',
        }}
      >
        <MiniTaskbar
          currentUser={currentUser}
          onCreateProject={() => navigate({ to: '/welcome' })}
          onOpenProfile={() => setProfileDialogOpen(true)}
          onOpenSettings={() => setProjectSettingsOpen(true)}
          onRequestLogout={() => setConfirmLogoutOpen(true)}
          mode="recreate"
          onSwitchMode={(mode) => {
            if (mode === 'autopost') {
              navigate({ to: '/autopost' });
              return;
            }
            navigate({ to: '/workspace' });
          }}
        />
      </Box>

      <Box
        sx={{
          order: { xs: 2, md: 1 },
          gridColumn: { md: 2 },
          minHeight: 0,
          borderRight: { xs: 'none', md: '1px solid #E5E7EB' },
          borderTop: { xs: '1px solid #E5E7EB', md: 'none' },
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box sx={{ display: { xs: 'block', md: 'none' } }}>
          <MiniTaskbar
            mobile
            currentUser={currentUser}
            onCreateProject={() => navigate({ to: '/welcome' })}
            onOpenProfile={() => setProfileDialogOpen(true)}
            onOpenSettings={() => setProjectSettingsOpen(true)}
            onRequestLogout={() => setConfirmLogoutOpen(true)}
            mode="recreate"
            onSwitchMode={(mode) => {
              if (mode === 'autopost') {
                navigate({ to: '/autopost' });
                return;
              }
              navigate({ to: '/workspace' });
            }}
          />
        </Box>
        {error && (
          <Alert severity="error" sx={{ borderRadius: 0, borderBottom: '1px solid #E5E7EB' }}>
            {error}
          </Alert>
        )}
        <RefinementSidebar
          messages={chatMessages}
          prompt={prompt}
          selectedModel={selectedModel}
          modelOptions={modelOptions}
          suggestions={REFINEMENT_SUGGESTIONS}
          loading={loadingWorkspace}
          refining={refining}
          showSuggestionChips={showSuggestionChips}
          onChangePrompt={setPrompt}
          onSelectModel={setSelectedModel}
          onSubmitPrompt={submitPrompt}
          onCancelPrompt={cancelRefinement}
          onSelectSuggestion={submitSuggestion}
        />
      </Box>

      <Box
        sx={{
          order: { xs: 1, md: 2 },
          minHeight: 0,
          gridColumn: { md: 3 },
        }}
      >
        <ResultWorkspacePanel
          campaignResult={campaignResult}
          loading={loadingResult}
          activeTab={activeTab}
          onChangeTab={setActiveTab}
          historyRuns={historyRuns}
          historyLoading={historyLoading}
          historyError={historyError}
          restoringRunId={restoringRunId}
          onRestoreRun={restoreFromRun}
          onPublishSocialPost={publishSocialPost}
          onGetFacebookPages={getFacebookPages}
          onOpenProfile={() => setProfileDialogOpen(true)}
        />
      </Box>

      <ProfileDialog
        open={profileDialogOpen}
        onClose={() => setProfileDialogOpen(false)}
      />
      <ProjectSettingsDialog
        open={projectSettingsOpen}
        onClose={() => setProjectSettingsOpen(false)}
      />

      <Dialog
        open={confirmLogoutOpen}
        onClose={() => setConfirmLogoutOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Logout</DialogTitle>
        <DialogContent>Are you sure you want to logout from this workspace?</DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button variant="outlined" onClick={() => setConfirmLogoutOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={handleLogout}>
            Logout
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
