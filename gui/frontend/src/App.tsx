import React, { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  Box,
  AppBar,
  Toolbar,
  Typography,
  Paper,
  Alert,
  Snackbar,
  Tabs,
  Tab,
  Button,
  Menu,
  MenuItem,
  IconButton
} from '@mui/material';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Settings, Dashboard, VpnKey, MoreVert } from '@mui/icons-material';

import LicenseForm from './components/LicenseForm';
import ConfigurationForm from './components/ConfigurationForm';
import AutomationDashboard from './components/AutomationDashboard';
import { ApiService } from './services/ApiService';
import { WebSocketService } from './services/WebSocketService';

// Create dark theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 500,
    },
  },
});

interface AppState {
  hasValidLicense: boolean;
  isConfigured: boolean;
  isLoading: boolean;
  error: string | null;
  licenseInfo: any;
  config: any;
}

const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState<AppState>({
    hasValidLicense: false,
    isConfigured: false,
    isLoading: true,
    error: null,
    licenseInfo: null,
    config: null,
  });
  
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);

  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'warning' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'info',
  });

  // Initialize app
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      setState(prev => ({ ...prev, isLoading: true }));

      // Check license status
      const licenseStatus = await ApiService.getLicenseStatus();
      const config = await ApiService.getConfiguration();

      setState(prev => ({
        ...prev,
        hasValidLicense: licenseStatus.has_license,
        isConfigured: config.gemini_api_key !== '',
        licenseInfo: licenseStatus.license_info,
        config: config,
        isLoading: false,
      }));

      // Initialize WebSocket if licensed
      if (licenseStatus.has_license) {
        WebSocketService.connect();
      }

    } catch (error) {
      setState(prev => ({
        ...prev,
        error: `Failed to initialize app: ${error}`,
        isLoading: false,
      }));
    }
  };

  const handleLicenseValidated = (licenseInfo: any) => {
    setState(prev => ({
      ...prev,
      hasValidLicense: true,
      licenseInfo: licenseInfo,
    }));
    
    // Initialize WebSocket after license validation
    WebSocketService.connect();
    
    showSnackbar('License validated successfully!', 'success');
    
    // Navigate to configuration page
    navigate('/configuration');
  };

  const handleConfigurationSaved = (config: any) => {
    setState(prev => ({
      ...prev,
      isConfigured: true,
      config: config,
    }));
    
    showSnackbar('Configuration saved successfully!', 'success');
    
    // Navigate to dashboard
    navigate('/dashboard');
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbar({
      open: true,
      message,
      severity,
    });
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  const getCurrentStep = () => {
    if (!state.hasValidLicense) return 'license';
    if (!state.isConfigured) return 'configuration';
    return 'dashboard';
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: string) => {
    navigate(newValue);
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setMenuAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
  };

  const handleMenuItemClick = (path: string) => {
    navigate(path);
    handleMenuClose();
  };

  const getCurrentTab = () => {
    if (location.pathname === '/configuration') return '/configuration';
    if (location.pathname === '/dashboard') return '/dashboard';
    if (location.pathname === '/license') return '/license';
    return '/dashboard';
  };

  if (state.isLoading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm">
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="100vh"
          >
            <Typography variant="h6">Loading Marketplace Magic...</Typography>
          </Box>
        </Container>
      </ThemeProvider>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Marketplace Magic
          </Typography>
          
          {/* Navigation Menu - Only show if licensed */}
          {state.hasValidLicense && (
            <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
              <Tabs
                value={getCurrentTab()}
                onChange={handleTabChange}
                textColor="inherit"
                indicatorColor="secondary"
                sx={{ minHeight: 'auto' }}
              >
                <Tab
                  icon={<Dashboard />}
                  label="Dashboard"
                  value="/dashboard"
                  sx={{ minHeight: 'auto', color: 'inherit' }}
                />
                <Tab
                  icon={<Settings />}
                  label="Configuration"
                  value="/configuration"
                  sx={{ minHeight: 'auto', color: 'inherit' }}
                />
              </Tabs>
              
              <IconButton
                color="inherit"
                onClick={handleMenuClick}
                sx={{ ml: 1 }}
              >
                <MoreVert />
              </IconButton>
              
              <Menu
                anchorEl={menuAnchorEl}
                open={Boolean(menuAnchorEl)}
                onClose={handleMenuClose}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
              >
                <MenuItem onClick={() => handleMenuItemClick('/license')}>
                  <VpnKey sx={{ mr: 1 }} />
                  License Settings
                </MenuItem>
              </Menu>
            </Box>
          )}
          
          <Typography variant="body2" color="inherit">
            {state.hasValidLicense ? 'Licensed' : 'Unlicensed'}
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        {state.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {state.error}
          </Alert>
        )}

        <Routes>
          <Route
            path="/"
            element={
              getCurrentStep() === 'license' ? (
                <Navigate to="/license" replace />
              ) : getCurrentStep() === 'configuration' ? (
                <Navigate to="/configuration" replace />
              ) : (
                <Navigate to="/dashboard" replace />
              )
            }
          />
          
          <Route
            path="/license"
            element={
              <Paper elevation={3} sx={{ p: 4 }}>
                <LicenseForm
                  onLicenseValidated={handleLicenseValidated}
                  onError={(error) => setState(prev => ({ ...prev, error }))}
                />
              </Paper>
            }
          />
          
          <Route
            path="/configuration"
            element={
              state.hasValidLicense ? (
                <Paper elevation={3} sx={{ p: 4 }}>
                  <ConfigurationForm
                    initialConfig={state.config}
                    onConfigurationSaved={handleConfigurationSaved}
                    onError={(error) => setState(prev => ({ ...prev, error }))}
                  />
                </Paper>
              ) : (
                <Navigate to="/license" replace />
              )
            }
          />
          
          <Route
            path="/dashboard"
            element={
              state.hasValidLicense ? (
                state.isConfigured ? (
                  <AutomationDashboard
                    config={state.config}
                    onError={(error) => setState(prev => ({ ...prev, error }))}
                  />
                ) : (
                  <Paper elevation={3} sx={{ p: 4 }}>
                    <Alert severity="warning" sx={{ mb: 2 }}>
                      Please configure your settings before using the dashboard.
                    </Alert>
                    <Button
                      variant="contained"
                      onClick={() => navigate('/configuration')}
                      startIcon={<Settings />}
                    >
                      Go to Configuration
                    </Button>
                  </Paper>
                )
              ) : (
                <Navigate to="/license" replace />
              )
            }
          />
        </Routes>
      </Container>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <AppContent />
      </Router>
    </ThemeProvider>
  );
};

export default App;