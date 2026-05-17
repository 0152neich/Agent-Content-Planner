import React, { useEffect } from 'react';
import { Box, Typography, Button, Container, Grid, Paper, AppBar, Toolbar } from '@mui/material';
import { motion, useAnimationControls } from 'framer-motion';
import { Brain, Search, PenTool, CheckCircle, ArrowRight } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/Common/LanguageSwitcher';
import { useSnackbar } from '@/components/AppLayout/SnackbarContext';
import brandLogo from '@/assets/app-logos/brand-logo.png';
import openAiLogo from '@/assets/ai-logos/openai.svg';
import geminiLogo from '@/assets/ai-logos/gemini.svg';
import anthropicLogo from '@/assets/ai-logos/anthropic.svg';
import grokLogo from '@/assets/ai-logos/grok.svg';
import copilotLogo from '@/assets/ai-logos/copilot.svg';

const AI_PLATFORMS = [
  { name: 'OpenAI', logo: openAiLogo },
  { name: 'Gemini', logo: geminiLogo },
  { name: 'Anthropic', logo: anthropicLogo },
  { name: 'Grok', logo: grokLogo },
  { name: 'Copilot', logo: copilotLogo },
];
const LOGO_ITEM_HEIGHT = 66;

export const LandingFeature: React.FC = () => {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const logoCarouselControls = useAnimationControls();

  const features = [
    {
      icon: Search,
      color: '#3fbff8',
      title: t('features.analyzer.title'),
      description: t('features.analyzer.description'),
    },
    {
      icon: Brain,
      color: '#66d7ff',
      title: t('features.strategist.title'),
      description: t('features.strategist.description'),
    },
    {
      icon: PenTool,
      color: '#2d98d6',
      title: t('features.copywriter.title'),
      description: t('features.copywriter.description'),
    },
    {
      icon: CheckCircle,
      color: '#8edfff',
      title: t('features.editor.title'),
      description: t('features.editor.description'),
    },
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15,
        delayChildren: 0.3,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.8,
        ease: [0.21, 0.47, 0.32, 0.98],
      },
    },
  };

  useEffect(() => {
    let isMounted = true;
    let currentIndex = 0;

    const sleep = (ms: number) => new Promise((resolve) => {
      setTimeout(resolve, ms);
    });

    const runCarousel = async () => {
      logoCarouselControls.set({ y: 0 });
      while (isMounted) {
        await sleep(1000);
        currentIndex += 1;
        await logoCarouselControls.start({
          y: -currentIndex * LOGO_ITEM_HEIGHT,
          transition: {
            duration: 0.7,
            ease: [0.24, 0.8, 0.2, 1],
          },
        });
        if (currentIndex >= AI_PLATFORMS.length) {
          await sleep(120);
          logoCarouselControls.set({ y: 0 });
          currentIndex = 0;
        }
      }
    };

    void runCarousel();
    return () => {
      isMounted = false;
    };
  }, [logoCarouselControls]);

  const notifyFeatureInDevelopment = () => {
    showSnackbar('Tính năng này chưa phát triển.', 'info');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        color: '#f8f8ff',
        background:
          'linear-gradient(180deg, rgba(255, 255, 255, 0.14) 0%, rgba(255, 255, 255, 0.02) 28%, rgba(255, 255, 255, 0) 52%), radial-gradient(150% 90% at 50% 100%, #4f2bc8 0%, rgba(79, 43, 200, 0.2) 52%, rgba(79, 43, 200, 0) 72%), linear-gradient(180deg, #090026 0%, #1c0a61 40%, #2f1a85 100%)',
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 0,
          background:
            'linear-gradient(180deg, rgba(255, 255, 255, 0) 38%, rgba(255, 255, 255, 0.12) 72%, rgba(255, 255, 255, 0.28) 100%)',
        }}
      />

      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 0,
          backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.22) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
          opacity: 0.36,
        }}
      />

      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          zIndex: 10,
          bgcolor: 'rgba(11, 4, 43, 0.6)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', py: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ width: 34, height: 34, borderRadius: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Box
                  component="img"
                  src={brandLogo}
                  alt="AI Content Planner logo"
                  sx={{ width: 32, height: 32, objectFit: 'contain' }}
                />
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 800, letterSpacing: '-0.02em', color: '#ffffff' }}>
                {t('common.appName')}
              </Typography>
            </Box>

            <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 3 }}>
              {['Platform', 'Resources', 'Docs', 'Pricing'].map((navItem) => (
                <Typography
                  key={navItem}
                  variant="body2"
                  onClick={notifyFeatureInDevelopment}
                  sx={{ color: 'rgba(255, 255, 255, 0.88)', fontWeight: 600, cursor: 'pointer' }}
                >
                  {navItem}
                </Typography>
              ))}
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 1, md: 2 } }}>
              <LanguageSwitcher />
              <Button
                component={Link}
                to="/login"
                variant="text"
                sx={{ fontWeight: 700, color: '#f5f3ff', borderRadius: '9999px', textTransform: 'none', minWidth: 'auto', px: 1.5 }}
              >
                Sign in
              </Button>
              <Button
                component={Link}
                to="/login"
                variant="contained"
                sx={{ fontWeight: 800, px: 3, borderRadius: '9999px', textTransform: 'none', bgcolor: '#ffffff', color: '#ffffff', '&:hover': { bgcolor: '#ece9ff' } }}
              >
                Get Started
              </Button>
            </Box>
          </Toolbar>
        </Container>
      </AppBar>

      <Box sx={{ pt: { xs: 14, md: 19 }, pb: { xs: 8, md: 14 }, flexGrow: 1, display: 'flex', alignItems: 'center', position: 'relative', overflow: 'hidden', zIndex: 1 }}>
        <Box sx={{ position: 'absolute', top: '2%', left: '-12%', width: '45vw', height: '45vw', background: 'radial-gradient(circle, rgba(78, 205, 255, 0.33) 0%, rgba(0,0,0,0) 65%)', filter: 'blur(95px)', zIndex: 0, pointerEvents: 'none' }} />
        <Box sx={{ position: 'absolute', top: '20%', right: '-10%', width: '46vw', height: '46vw', background: 'radial-gradient(circle, rgba(121, 84, 255, 0.3) 0%, rgba(0,0,0,0) 65%)', filter: 'blur(100px)', zIndex: 0, pointerEvents: 'none' }} />

        <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
          <motion.div initial="hidden" animate="visible" variants={containerVariants} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
            <motion.div variants={itemVariants}>
              <Typography
                variant="h1"
                sx={{
                  fontSize: { xs: '2.2rem', sm: '2.9rem', md: '4.6rem' },
                  fontWeight: 800,
                  lineHeight: 1.08,
                  mb: 2,
                  color: '#ffffff',
                  letterSpacing: '-0.03em',
                  maxWidth: 1100,
                }}
              >
                Plan, Create, and Scale Content with
              </Typography>
            </motion.div>

            <motion.div variants={itemVariants}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2.2, mb: 3.5, flexWrap: 'wrap' }}>
                <Box sx={{ width: 66, height: 66, borderRadius: '18px', background: '#ffffff', overflow: 'hidden', boxShadow: '0 20px 35px rgba(6, 5, 25, 0.35)' }}>
                  <motion.div animate={logoCarouselControls}>
                    {[...AI_PLATFORMS, AI_PLATFORMS[0]].map((platform, index) => (
                      <Box key={`${platform.name}-${index}`} sx={{ height: LOGO_ITEM_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Box
                          component="img"
                          src={platform.logo}
                          alt={`${platform.name} logo`}
                          sx={{ width: 54, height: 54, objectFit: 'contain', filter: 'saturate(1.08) contrast(1.04)' }}
                        />
                      </Box>
                    ))}
                  </motion.div>
                </Box>
                <Typography variant="h2" sx={{ fontSize: { xs: '2.5rem', md: '4.3rem' }, fontWeight: 800, letterSpacing: '-0.03em', color: '#ffffff', lineHeight: 1 }}>
                  AI Agents
                </Typography>
              </Box>
            </motion.div>

            <motion.div variants={itemVariants}>
              <Typography
                variant="h6"
                sx={{ color: 'rgba(235, 231, 255, 0.92)', fontWeight: 500, mb: 5.5, maxWidth: 930, mx: 'auto', lineHeight: 1.6, fontSize: { xs: '1rem', md: '1.55rem' } }}
              >
                AI Content Planner transforms a single URL into a full content workflow. Our multi-agent system researches your market, builds strategy, and drafts platform-ready content for SEO, social, and campaigns in minutes.
              </Typography>
            </motion.div>

            <motion.div variants={itemVariants}>
              <Box sx={{ display: 'flex', gap: 2.2, flexDirection: { xs: 'column', sm: 'row' }, width: { xs: '100%', sm: 'auto' }, justifyContent: 'center' }}>
                <Button
                  component={Link}
                  to="/login"
                  variant="contained"
                  size="large"
                  endIcon={<ArrowRight size={18} />}
                  sx={{ py: 1.7, px: 5, fontSize: '1.02rem', borderRadius: '9999px', fontWeight: 700, textTransform: 'none', boxShadow: '0 16px 24px rgba(16, 9, 57, 0.35)', bgcolor: '#ffffff', color: '#1b1348', '&:hover': { bgcolor: '#ece9ff' } }}
                >
                  {t('landing.startTrial')}
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  onClick={notifyFeatureInDevelopment}
                  sx={{ py: 1.7, px: 5, fontSize: '1.02rem', borderRadius: '9999px', fontWeight: 700, textTransform: 'none', bgcolor: 'rgba(255, 255, 255, 0.2)', color: '#f8f5ff', '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.32)' } }}
                >
                  Book a Demo
                </Button>
              </Box>
            </motion.div>
          </motion.div>
        </Container>
      </Box>

      <Box sx={{ py: { xs: 10, md: 14 }, bgcolor: 'transparent', position: 'relative', zIndex: 1 }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 10 }}>
            <Typography variant="h3" sx={{ mb: 2, fontWeight: 800, color: '#ffffff' }}>
              {t('landing.architectureTitle')}
            </Typography>
            <Typography variant="body1" sx={{ maxWidth: 720, mx: 'auto', lineHeight: 1.8, fontSize: '1.1rem', color: 'rgba(239, 235, 255, 0.8)' }}>
              {t('landing.architectureSub')}
            </Typography>
          </Box>

          <Grid container spacing={4} alignItems="stretch">
            {features.map((feature, index) => (
              <Grid item xs={12} sm={6} md={3} key={index} sx={{ display: 'flex' }}>
                <Box component={motion.div} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-100px' }} transition={{ duration: 0.6, delay: index * 0.1 }} sx={{ display: 'flex', width: '100%' }}>
                  <Paper
                    sx={{
                      p: 4.5,
                      width: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      borderRadius: 4,
                      bgcolor: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.14)',
                      backdropFilter: 'blur(10px)',
                      boxShadow: '0 20px 40px rgba(8, 4, 26, 0.25)',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      '&:hover': {
                        transform: 'translateY(-8px)',
                        boxShadow: `0 20px 25px -5px ${feature.color}25`,
                        borderColor: `${feature.color}40`,
                      },
                    }}
                  >
                    <Box sx={{ width: 48, height: 48, borderRadius: 2, bgcolor: `${feature.color}10`, color: feature.color, display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 3.5 }}>
                      <feature.icon size={26} />
                    </Box>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 800, color: '#ffffff' }}>
                      {feature.title}
                    </Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.7, flexGrow: 1, fontSize: '0.95rem', color: 'rgba(237, 231, 255, 0.8)' }}>
                      {feature.description}
                    </Typography>
                  </Paper>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      <Box sx={{ py: 6, borderTop: '1px solid rgba(255, 255, 255, 0.14)', zIndex: 1 }}>
        <Container
          maxWidth="lg"
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 500, color: 'rgba(241, 237, 255, 0.76)' }}>
            © 2026 AI Content Planner.
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <Typography
              variant="body2"
              onClick={notifyFeatureInDevelopment}
              sx={{ fontWeight: 500, color: 'rgba(241, 237, 255, 0.76)', cursor: 'pointer' }}
            >
              Terms
            </Typography>
            <Typography
              variant="body2"
              onClick={notifyFeatureInDevelopment}
              sx={{ fontWeight: 500, color: 'rgba(241, 237, 255, 0.76)', cursor: 'pointer' }}
            >
              Privacy Policy
            </Typography>
          </Box>
        </Container>
      </Box>
    </Box>
  );
};
