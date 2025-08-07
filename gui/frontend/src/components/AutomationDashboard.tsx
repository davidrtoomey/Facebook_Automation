import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Collapse,
  Badge,
  TextField,
  Switch,
  FormControlLabel,
  FormGroup,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Refresh,
  CheckCircle,
  Error,
  Info,
  ExpandMore,
  ExpandLess,
  Settings,
  Timeline,
  Chat,
  AttachMoney,
  People,
  Terminal,
  Clear,
  Search,
  Visibility,
  VisibilityOff,
  Close,
  OpenInNew,
  Schedule,
  Person,
  Message,
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import { WebSocketService } from '../services/WebSocketService';

interface AutomationDashboardProps {
  config: any;
  onError: (error: string) => void;
}

interface AutomationResult {
  url: string;
  status: 'offer_sent' | 'negotiating' | 'accepted' | 'rejected' | 'error';
  message: string;
  timestamp: string;
  offer_amount?: number;
  type: 'offer' | 'conversation';
}

interface AutomationStatus {
  is_running: boolean;
  current_step: string;
  progress: number;
  message: string;
  status: 'idle' | 'running' | 'completed' | 'error';
}

const AutomationDashboard: React.FC<AutomationDashboardProps> = ({ config, onError }) => {
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus>({
    is_running: false,
    current_step: '',
    progress: 0,
    message: 'Ready to start',
    status: 'idle',
  });
  
  const [results, setResults] = useState<AutomationResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [selectedResult, setSelectedResult] = useState<AutomationResult | null>(null);
  const [stats, setStats] = useState({
    total_conversations: 0,
    offers_sent: 0,
    negotiations_active: 0,
    deals_completed: 0,
    total_listings: 0,
  });
  const [progressInfo, setProgressInfo] = useState({
    has_progress: false,
    message: '',
    next_product: null,
    progress_percentage: 0,
  });
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [showConsole, setShowConsole] = useState(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [headlessOffers, setHeadlessOffers] = useState<boolean>(true);
  const [headlessConversations, setHeadlessConversations] = useState<boolean>(true);
  
  // Pricing settings state
  const [marginPercent, setMarginPercent] = useState<number>(20);
  const [pricingData, setPricingData] = useState<any>(null);
  const [pricingLoading, setPricingLoading] = useState<boolean>(false);
  
  // Modal states
  const [showListingsModal, setShowListingsModal] = useState(false);
  const [showOffersModal, setShowOffersModal] = useState(false);
  const [showNegotiationsModal, setShowNegotiationsModal] = useState(false);
  const [detailedData, setDetailedData] = useState<any>(null);
  const [modalLoading, setModalLoading] = useState(false);
  
  const consoleEndRef = useRef<HTMLDivElement>(null);
  const consoleContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll console to bottom when new logs are added (only within console container)
  useEffect(() => {
    if (consoleContainerRef.current && showConsole) {
      const container = consoleContainerRef.current;
      // Only auto-scroll if user is already near the bottom (within 100px)
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      
      if (isNearBottom) {
        // Scroll only within the console container, not the entire page
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [consoleLogs, showConsole]);

  useEffect(() => {
    // Initialize WebSocket listeners
    const messageHandler = (data: any) => {
      if (data.type === 'progress') {
        // Debug logging to understand what status values we're getting
        console.log('[AUTOMATION DEBUG] WebSocket progress data:', {
          status: data.status,
          is_running: data.is_running,
          message: data.message
        });
        
        setAutomationStatus(prev => {
          // Determine is_running based on multiple conditions
          const isActiveAutomation = data.status === 'running' || 
                                   data.is_running === true || 
                                   (prev.is_running && data.status !== 'completed' && data.status !== 'error' && data.status !== 'idle');
          
          console.log('[AUTOMATION DEBUG] Setting is_running to:', isActiveAutomation);
          
          return {
            ...prev,
            status: data.status,
            progress: data.progress,
            message: data.message,
            current_step: data.current_step || prev.current_step,
            is_running: isActiveAutomation,
          };
        });
      } else if (data.type === 'result') {
        console.log('[STATS DEBUG] Received WebSocket result:', data.result);
        setResults(prev => [...prev, data.result]);
        updateStats(data.result);
      } else if (data.type === 'console') {
        setConsoleLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`]);
      } else if (data.type === 'error') {
        setAutomationStatus(prev => ({
          ...prev,
          status: 'error',
          message: data.message,
        }));
        onError(data.message);
      }
    };
    
    WebSocketService.onMessage(messageHandler);

    // Load initial data
    loadInitialData();

    // Refresh statistics every 30 seconds to keep negotiations count accurate
    const statsRefreshInterval = setInterval(() => {
      if (!automationStatus.is_running) {
        // Only refresh when not running automation to avoid conflicts
        loadInitialData();
      }
    }, 30000);

    return () => {
      // Only remove the message handler, don't disconnect WebSocket
      WebSocketService.removeMessageHandler(messageHandler);
      clearInterval(statsRefreshInterval);
    };
  }, []);

  const loadInitialData = async () => {
    try {
      const status = await ApiService.getAutomationStatus();
      setAutomationStatus(status);
      
      // Load existing statistics from files
      const statistics = await ApiService.getStatistics();
      setStats(statistics);
      
      // Load automation progress information
      const progress = await ApiService.getAutomationProgress();
      setProgressInfo(progress);
      
      // Load configuration to get headless settings
      const configuration = await ApiService.getConfiguration();
      setHeadlessOffers(configuration.headless_offers ?? true);
      setHeadlessConversations(configuration.headless_conversations ?? true);
      
    } catch (error) {
      onError(`Failed to load automation status: ${error}`);
    }
  };

  const updateStats = (result: AutomationResult) => {
    console.log('[STATS DEBUG] Updating stats with result:', result);
    console.log('[STATS DEBUG] Result type:', result.type, 'Status:', result.status);
    
    setStats(prev => {
      const newStats = {
        ...prev,
        // Only increment cumulative counters for offers and completed deals
        offers_sent: result.type === 'offer' ? prev.offers_sent + 1 : prev.offers_sent,
        deals_completed: result.status === 'accepted' ? prev.deals_completed + 1 : prev.deals_completed,
        // Note: negotiations_active and total_conversations should be based on file data, not incremented
        // Real-time updates are just for immediate feedback, file-based stats are authoritative
      };
      
      console.log('[STATS DEBUG] Previous stats:', prev);
      console.log('[STATS DEBUG] New stats:', newStats);
      return newStats;
    });
  };

  const handleStartAutomation = async () => {
    try {
      setAutomationStatus(prev => ({ ...prev, is_running: true, status: 'running' }));
      setResults([]);
      // Don't reset stats - keep cumulative count from file-based statistics
      setConsoleLogs([]);
      
      await ApiService.startAutomation(config);
    } catch (error) {
      setAutomationStatus(prev => ({ ...prev, is_running: false, status: 'error' }));
      onError(`Failed to start automation: ${error}`);
    }
  };

  const handleStopAutomation = async () => {
    try {
      await ApiService.stopAutomation();
      setAutomationStatus(prev => ({ ...prev, is_running: false, status: 'idle' }));
    } catch (error) {
      onError(`Failed to stop automation: ${error}`);
    }
  };

  const handleRunOffers = async () => {
    try {
      setAutomationStatus(prev => ({ ...prev, is_running: true, status: 'running' }));
      setResults([]);
      // Don't reset stats - keep cumulative count from file-based statistics
      setConsoleLogs([]);
      
      await ApiService.runOffersOnly(config, headlessOffers);
    } catch (error) {
      setAutomationStatus(prev => ({ ...prev, is_running: false, status: 'error' }));
      onError(`Failed to start offer agent: ${error}`);
    }
  };

  const handleRunConversations = async () => {
    try {
      setAutomationStatus(prev => ({ ...prev, is_running: true, status: 'running' }));
      setResults([]);
      // Don't reset stats - keep cumulative count from file-based statistics
      setConsoleLogs([]);
      
      await ApiService.runConversationsOnly(config, headlessConversations);
    } catch (error) {
      setAutomationStatus(prev => ({ ...prev, is_running: false, status: 'error' }));
      onError(`Failed to start conversation agent: ${error}`);
    }
  };

  const handleScrapeListings = async () => {
    try {
      if (!searchTerm.trim()) {
        onError('Please enter a search term');
        return;
      }
      
      setAutomationStatus(prev => ({ ...prev, is_running: true, status: 'running' }));
      setResults([]);
      // Don't reset stats - keep cumulative count from file-based statistics
      setConsoleLogs([]);
      
      await ApiService.scrapeListingsOnly(searchTerm.trim(), config);
    } catch (error) {
      setAutomationStatus(prev => ({ ...prev, is_running: false, status: 'error' }));
      onError(`Failed to start listing scraper: ${error}`);
    }
  };

  const handleResetProgress = async () => {
    try {
      await ApiService.resetAutomationProgress();
      // Reload progress information
      const progress = await ApiService.getAutomationProgress();
      setProgressInfo(progress);
      onError('Automation progress reset successfully!'); // Using onError for notification, might want a success handler
    } catch (error) {
      onError(`Failed to reset automation progress: ${error}`);
    }
  };

  // Pricing handlers
  const handleUpdatePricing = async () => {
    setPricingLoading(true);
    try {
      const response = await fetch('/api/update-pricing', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ margin_percent: marginPercent }),
      });
      
      if (!response.ok) {
        throw new globalThis.Error('Failed to update pricing');
      }
      
      const result = await response.json();
      setPricingData(result);
      onError(`Pricing updated successfully with ${marginPercent}% margin!`);
    } catch (error) {
      onError(`Failed to update pricing: ${error}`);
    } finally {
      setPricingLoading(false);
    }
  };

  const handleFetchPricing = async () => {
    setPricingLoading(true);
    try {
      const response = await fetch('/api/run-pricing-script', {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new globalThis.Error('Failed to fetch pricing data');
      }
      
      const result = await response.json();
      onError('Pricing data fetched from Google Sheets successfully!');
      // Automatically update pricing with current margin
      setTimeout(() => handleUpdatePricing(), 1000);
    } catch (error) {
      onError(`Failed to fetch pricing data: ${error}`);
    } finally {
      setPricingLoading(false);
    }
  };

  // Modal handlers
  const handleShowListings = async () => {
    setModalLoading(true);
    setShowListingsModal(true);
    try {
      const data = await ApiService.getDetailedListings();
      setDetailedData(data);
    } catch (error) {
      onError(`Failed to load listings data: ${error}`);
    } finally {
      setModalLoading(false);
    }
  };

  const handleShowOffers = async () => {
    setModalLoading(true);
    setShowOffersModal(true);
    try {
      const data = await ApiService.getDetailedOffers();
      setDetailedData(data);
    } catch (error) {
      onError(`Failed to load offers data: ${error}`);
    } finally {
      setModalLoading(false);
    }
  };

  const handleShowNegotiations = async () => {
    setModalLoading(true);
    setShowNegotiationsModal(true);
    try {
      const data = await ApiService.getDetailedNegotiations();
      setDetailedData(data);
    } catch (error) {
      onError(`Failed to load negotiations data: ${error}`);
    } finally {
      setModalLoading(false);
    }
  };

  const closeModal = () => {
    setShowListingsModal(false);
    setShowOffersModal(false);
    setShowNegotiationsModal(false);
    setDetailedData(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'offer_sent': return 'primary';
      case 'negotiating': return 'warning';
      case 'accepted': return 'success';
      case 'rejected': return 'error';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'offer_sent': return <Info />;
      case 'negotiating': return <Chat />;
      case 'accepted': return <CheckCircle />;
      case 'rejected': return <Error />;
      case 'error': return <Error />;
      default: return <Info />;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      <Box textAlign="center" mb={4}>
        <Timeline sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
        <Typography variant="h4" gutterBottom>
          Automation Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor and control your marketplace automation
        </Typography>
      </Box>

      {/* Control Panel */}
      <Card sx={{ 
        mb: 3,
        background: 'linear-gradient(135deg, rgba(25,118,210,0.05) 0%, rgba(156,39,176,0.05) 100%)',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
        backdropFilter: 'blur(10px)',
      }}>
        <CardContent sx={{ p: 4 }}>
          <Box display="flex" alignItems="center" gap={2} mb={4}>
            <Box sx={{
              p: 2,
              borderRadius: 2,
              background: 'linear-gradient(135deg, #1976d2 0%, #9c27b0 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Settings sx={{ color: 'white', fontSize: 28 }} />
            </Box>
            <Typography variant="h5" fontWeight="600" sx={{
              background: 'linear-gradient(135deg, #1976d2 0%, #9c27b0 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              Control Panel
            </Typography>
          </Box>
          
          {/* Search Section */}
          <Box mb={4}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <Search sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" color="primary.main" fontWeight="500">
                Search Configuration
              </Typography>
            </Box>
            <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
              <TextField
                size="medium"
                label="Search Term"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                disabled={automationStatus.is_running}
                sx={{ 
                  minWidth: '300px', 
                  flex: 1,
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                    background: 'rgba(255,255,255,0.05)',
                    '&:hover': {
                      background: 'rgba(255,255,255,0.08)',
                    }
                  }
                }}
                placeholder="Search Term"
              />
              <Button
                variant="contained"
                startIcon={<Search />}
                onClick={handleScrapeListings}
                disabled={automationStatus.is_running}
                sx={{ 
                  minWidth: '160px',
                  height: '56px',
                  borderRadius: 2,
                  background: 'linear-gradient(135deg, #4caf50 0%, #45a049 100%)',
                  boxShadow: '0 4px 15px rgba(76,175,80,0.3)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #45a049 0%, #3e8e41 100%)',
                    boxShadow: '0 6px 20px rgba(76,175,80,0.4)',
                    transform: 'translateY(-2px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                Scrape Listings
              </Button>
            </Box>
          </Box>

          {/* Headless Mode Configuration */}
          <Box mb={4}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <Visibility sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" color="primary.main" fontWeight="500">
                Browser Visibility Settings
              </Typography>
            </Box>
            <FormGroup>
              <Box display="flex" gap={4} alignItems="center" flexWrap="wrap">
                <FormControlLabel
                  control={
                    <Switch
                      checked={!headlessOffers}
                      onChange={(e) => setHeadlessOffers(!e.target.checked)}
                      disabled={automationStatus.is_running}
                      color="primary"
                    />
                  }
                  label={
                    <Box display="flex" alignItems="center" gap={1}>
                      {headlessOffers ? <VisibilityOff /> : <Visibility />}
                      <Typography variant="body2">
                        Show Offer Agent Browser
                      </Typography>
                    </Box>
                  }
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={!headlessConversations}
                      onChange={(e) => setHeadlessConversations(!e.target.checked)}
                      disabled={automationStatus.is_running}
                      color="primary"
                    />
                  }
                  label={
                    <Box display="flex" alignItems="center" gap={1}>
                      {headlessConversations ? <VisibilityOff /> : <Visibility />}
                      <Typography variant="body2">
                        Show Conversation Agent Browser
                      </Typography>
                    </Box>
                  }
                />
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                Toggle browser visibility for debugging and monitoring. Headless mode (hidden browser) is faster but shows no visual feedback.
              </Typography>
            </FormGroup>
          </Box>

          {/* Pricing Settings */}
          <Box mb={4}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <AttachMoney sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" color="primary.main" fontWeight="500">
                Pricing & Margin Settings
              </Typography>
            </Box>
            <Box display="flex" gap={2} alignItems="center" flexWrap="wrap" mb={2}>
              <TextField
                size="medium"
                label="Profit Margin (%)"
                type="number"
                value={marginPercent}
                onChange={(e) => setMarginPercent(Math.max(0, Math.min(50, parseInt(e.target.value) || 0)))}
                disabled={automationStatus.is_running || pricingLoading}
                inputProps={{ min: 0, max: 50, step: 1 }}
                sx={{ 
                  width: '200px',
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                    background: 'rgba(255,255,255,0.05)',
                    '&:hover': {
                      background: 'rgba(255,255,255,0.08)',
                    }
                  }
                }}
                helperText="Your profit margin (0-50%)"
              />
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={handleFetchPricing}
                disabled={automationStatus.is_running || pricingLoading}
                sx={{ 
                  minWidth: '180px',
                  height: '56px',
                  borderRadius: 2,
                  background: 'linear-gradient(135deg, #2196f3 0%, #1976d2 100%)',
                  boxShadow: '0 4px 15px rgba(33,150,243,0.3)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
                    boxShadow: '0 6px 20px rgba(33,150,243,0.4)',
                    transform: 'translateY(-2px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                {pricingLoading ? 'Fetching...' : 'Fetch Pricing'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<AttachMoney />}
                onClick={handleUpdatePricing}
                disabled={automationStatus.is_running || pricingLoading}
                sx={{ 
                  minWidth: '160px',
                  height: '56px',
                  borderRadius: 2,
                  borderColor: 'primary.main',
                  color: 'primary.main',
                  '&:hover': {
                    borderColor: 'primary.dark',
                    background: 'rgba(33,150,243,0.1)',
                    transform: 'translateY(-1px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                {pricingLoading ? 'Updating...' : 'Update Margin'}
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Fetch pricing data from Google Sheets and set your profit margin. Higher margins = lower offers to sellers.
            </Typography>
            {pricingData && (
              <Box mt={2} p={2} sx={{ background: 'rgba(76,175,80,0.1)', borderRadius: 2, border: '1px solid rgba(76,175,80,0.3)' }}>
                <Typography variant="body2" color="success.main" fontWeight="500">
                  ✅ Pricing data loaded: {pricingData.total_models || 0} iPhone models with {marginPercent}% margin applied
                </Typography>
              </Box>
            )}
          </Box>

          {/* Main Action Buttons */}
          <Box mb={4}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <PlayArrow sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" color="primary.main" fontWeight="500">
                Automation Actions
              </Typography>
            </Box>
            <Box display="flex" gap={3} alignItems="center" flexWrap="wrap">
              <Button
                variant="contained"
                startIcon={<PlayArrow />}
                onClick={handleStartAutomation}
                disabled={automationStatus.is_running}
                size="large"
                sx={{ 
                  minWidth: '180px',
                  height: '56px',
                  borderRadius: 2,
                  background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
                  boxShadow: '0 4px 15px rgba(25,118,210,0.3)',
                  fontSize: '16px',
                  fontWeight: '600',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #1565c0 0%, #0d47a1 100%)',
                    boxShadow: '0 6px 20px rgba(25,118,210,0.4)',
                    transform: 'translateY(-2px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                Start Automation
              </Button>
              <Button
                variant="contained"
                startIcon={<AttachMoney />}
                onClick={handleRunOffers}
                disabled={automationStatus.is_running}
                sx={{ 
                  minWidth: '180px',
                  height: '56px',
                  borderRadius: 2,
                  background: 'linear-gradient(135deg, #e91e63 0%, #c2185b 100%)',
                  boxShadow: '0 4px 15px rgba(233,30,99,0.3)',
                  fontSize: '16px',
                  fontWeight: '600',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #c2185b 0%, #ad1457 100%)',
                    boxShadow: '0 6px 20px rgba(233,30,99,0.4)',
                    transform: 'translateY(-2px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                Start Offer Agent
              </Button>
              <Button
                variant="contained"
                startIcon={<Chat />}
                onClick={handleRunConversations}
                disabled={automationStatus.is_running}
                sx={{ 
                  minWidth: '200px',
                  height: '56px',
                  borderRadius: 2,
                  background: 'linear-gradient(135deg, #00bcd4 0%, #0097a7 100%)',
                  boxShadow: '0 4px 15px rgba(0,188,212,0.3)',
                  fontSize: '16px',
                  fontWeight: '600',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #0097a7 0%, #00838f 100%)',
                    boxShadow: '0 6px 20px rgba(0,188,212,0.4)',
                    transform: 'translateY(-2px)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                Start Negotiation Agent
              </Button>
            </Box>
          </Box>

          {/* Control Buttons */}
          <Box display="flex" gap={2} alignItems="center" justifyContent="flex-end" pt={2} borderTop="1px solid rgba(255,255,255,0.1)">
            <Button
              variant="outlined"
              startIcon={<Stop />}
              onClick={() => {
                console.log('[STOP BUTTON DEBUG] Current automation status:', automationStatus);
                console.log('[STOP BUTTON DEBUG] is_running:', automationStatus.is_running);
                console.log('[STOP BUTTON DEBUG] FORCE STOPPING - button always enabled');
                handleStopAutomation();
              }}
              disabled={false}  // ALWAYS ENABLED - critical for emergency stop
              sx={{ 
                minWidth: '120px',
                height: '48px',
                borderRadius: 2,
                borderColor: '#f44336',
                color: '#f44336',
                borderWidth: '2px',
                fontWeight: '600',
                opacity: automationStatus.is_running ? 1.0 : 0.6,  // Visual feedback
                '&:hover': {
                  borderColor: '#d32f2f',
                  backgroundColor: 'rgba(244,67,54,0.1)',
                  borderWidth: '2px',
                  transform: 'translateY(-1px)',
                  opacity: 1.0,  // Full opacity on hover
                },
                '&:disabled': {
                  opacity: 0.3,  // This shouldn't happen anymore
                },
                transition: 'all 0.3s ease',
              }}
            >
              Stop
            </Button>
            <IconButton 
              onClick={loadInitialData} 
              disabled={automationStatus.is_running}
              sx={{
                background: 'linear-gradient(135deg, #1976d2 0%, #9c27b0 100%)',
                color: 'white',
                width: 48,
                height: 48,
                '&:hover': {
                  background: 'linear-gradient(135deg, #1565c0 0%, #7b1fa2 100%)',
                  transform: 'rotate(180deg) scale(1.1)',
                },
                transition: 'all 0.5s ease',
              }}
            >
              <Refresh />
            </IconButton>
          </Box>

          {/* Status Display */}
          {automationStatus.status !== 'idle' && (
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="body1">
                  Status: {automationStatus.current_step || automationStatus.message}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {automationStatus.progress}%
                </Typography>
              </Box>
              <LinearProgress 
                variant="determinate" 
                value={automationStatus.progress} 
                sx={{ mb: 2 }}
              />
              {automationStatus.status === 'error' && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {automationStatus.message}
                </Alert>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Progress Information - HIDDEN: Using Control Panel status instead */}
      {false && progressInfo.has_progress && (
        <Card sx={{ 
          mb: 3,
          background: 'linear-gradient(135deg, rgba(76,175,80,0.05) 0%, rgba(56,142,60,0.05) 100%)',
          border: '1px solid rgba(76,175,80,0.2)',
          boxShadow: '0 8px 32px rgba(76,175,80,0.1)',
        }}>
          <CardContent sx={{ p: 3 }}>
            <Box display="flex" alignItems="center" gap={2} mb={2}>
              <Box sx={{
                p: 1.5,
                borderRadius: 2,
                background: 'linear-gradient(135deg, #4caf50 0%, #388e3c 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Timeline sx={{ color: 'white', fontSize: 24 }} />
              </Box>
              <Typography variant="h6" fontWeight="600" sx={{
                background: 'linear-gradient(135deg, #4caf50 0%, #388e3c 100%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                Automation Progress
              </Typography>
            </Box>
            
            <Typography variant="body1" sx={{ mb: 2, fontWeight: 500 }}>
              {progressInfo.message}
            </Typography>
            
            {progressInfo.next_product && (
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Typography variant="body2" color="text.secondary">
                  Next Product:
                </Typography>
                <Chip 
                  label={progressInfo.next_product} 
                  color="primary" 
                  size="small"
                  sx={{ fontWeight: 600 }}
                />
              </Box>
            )}
            
            {progressInfo.progress_percentage > 0 && (
              <Box sx={{ mb: 2 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="body2" color="text.secondary">
                    Cycle Progress
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {progressInfo.progress_percentage}%
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={progressInfo.progress_percentage}
                  sx={{ 
                    height: 8,
                    borderRadius: 4,
                    backgroundColor: 'rgba(76,175,80,0.1)',
                    '& .MuiLinearProgress-bar': {
                      background: 'linear-gradient(135deg, #4caf50 0%, #388e3c 100%)',
                      borderRadius: 4,
                    }
                  }}
                />
              </Box>
            )}
            
            <Box display="flex" justifyContent="flex-end">
              <Button
                variant="outlined"
                size="small"
                onClick={handleResetProgress}
                disabled={automationStatus.is_running}
                sx={{
                  borderColor: '#4caf50',
                  color: '#4caf50',
                  '&:hover': {
                    borderColor: '#388e3c',
                    backgroundColor: 'rgba(76,175,80,0.1)',
                  }
                }}
              >
                Reset Progress
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Statistics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card 
            sx={{ 
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: '0 8px 25px rgba(0,0,0,0.15)',
                backgroundColor: 'rgba(25, 118, 210, 0.04)',
              }
            }}
            onClick={handleShowNegotiations}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={2}>
                <People color="primary" />
                <Box flex={1}>
                  <Typography variant="h4">{stats.total_conversations}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Conversations
                  </Typography>
                </Box>
                <OpenInNew sx={{ color: 'text.secondary', fontSize: 20 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card 
            sx={{ 
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: '0 8px 25px rgba(0,0,0,0.15)',
                backgroundColor: 'rgba(76, 175, 80, 0.04)',
              }
            }}
            onClick={handleShowOffers}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={2}>
                <AttachMoney color="primary" />
                <Box flex={1}>
                  <Typography variant="h4">{stats.offers_sent}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Offers Sent
                  </Typography>
                </Box>
                <OpenInNew sx={{ color: 'text.secondary', fontSize: 20 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card 
            sx={{ 
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: '0 8px 25px rgba(0,0,0,0.15)',
                backgroundColor: 'rgba(255, 152, 0, 0.04)',
              }
            }}
            onClick={handleShowNegotiations}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={2}>
                <Badge badgeContent={stats.negotiations_active} color="warning">
                  <Chat color="primary" />
                </Badge>
                <Box flex={1}>
                  <Typography variant="h4">{stats.negotiations_active}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Active Negotiations
                  </Typography>
                </Box>
                <OpenInNew sx={{ color: 'text.secondary', fontSize: 20 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card 
            sx={{ 
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: '0 8px 25px rgba(0,0,0,0.15)',
                backgroundColor: 'rgba(76, 175, 80, 0.04)',
              }
            }}
            onClick={handleShowListings}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={2}>
                <Search color="primary" />
                <Box flex={1}>
                  <Typography variant="h4">{stats.total_listings || 0}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Listings
                  </Typography>
                </Box>
                <OpenInNew sx={{ color: 'text.secondary', fontSize: 20 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Console Output */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box display="flex" alignItems="center" gap={1}>
              <Terminal />
              <Typography variant="h6">Console Output</Typography>
            </Box>
            <Box display="flex" gap={1}>
              <IconButton 
                onClick={() => setConsoleLogs([])} 
                disabled={consoleLogs.length === 0}
                title="Clear logs"
              >
                <Clear />
              </IconButton>
              <IconButton onClick={() => setShowConsole(!showConsole)}>
                {showConsole ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            </Box>
          </Box>
          
          <Collapse in={showConsole}>
            <Paper 
              ref={consoleContainerRef}
              variant="outlined" 
              sx={{ 
                p: 2, 
                backgroundColor: '#1a1a1a', 
                color: '#00ff00',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                maxHeight: '400px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap'
              }}
            >
              {consoleLogs.length > 0 ? (
                <>
                  {consoleLogs.map((log, index) => (
                    <div key={index}>{log}</div>
                  ))}
                  <div ref={consoleEndRef} />
                </>
              ) : (
                <Typography 
                  variant="body2" 
                  color="text.secondary" 
                  sx={{ fontFamily: 'monospace' }}
                >
                  Console output will appear here when automation starts...
                </Typography>
              )}
            </Paper>
          </Collapse>
        </CardContent>
      </Card>

      {/* Configuration Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Current Configuration</Typography>
            <IconButton onClick={() => setShowResults(!showResults)}>
              {showResults ? <ExpandLess /> : <ExpandMore />}
            </IconButton>
          </Box>
          <Collapse in={showResults}>
            <Box mt={2}>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">Search Products:</Typography>
                  <Box display="flex" flexWrap="wrap" gap={1} mt={1}>
                    {config.search_products?.map((product: any) => (
                      <Chip 
                        key={product.name || product} 
                        label={product.name || product} 
                        size="small" 
                      />
                    ))}
                  </Box>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">Pricing:</Typography>
                  <Box mt={1}>
                    {config.search_products?.length > 0 && (
                      <Typography variant="body2">
                        First Product: Unlocked ${config.search_products[0]?.base_offer_unlocked || 'N/A'} | 
                        Locked ${config.search_products[0]?.base_offer_locked || 'N/A'}
                      </Typography>
                    )}
                    <Typography variant="body2">
                      Flexibility: ${config.price_flexibility || 'N/A'}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">Limits:</Typography>
                  <Typography variant="body2">
                    Max Conversations: {config.max_conversations}
                  </Typography>
                  <Typography variant="body2">
                    Max Offers per Run: {config.max_offers_per_run}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">Settings:</Typography>
                  <Typography variant="body2">
                    Strategy: {config.strategy}
                  </Typography>
                  <Typography variant="body2">
                    Negotiation: {config.enable_negotiation ? 'Enabled' : 'Disabled'}
                  </Typography>
                  <Typography variant="body2">
                    Offer Agent: {headlessOffers ? 'Headless' : 'Visible'}
                  </Typography>
                  <Typography variant="body2">
                    Conversation Agent: {headlessConversations ? 'Headless' : 'Visible'}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </Collapse>
        </CardContent>
      </Card>

      {/* Results Table */}
      {results.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Recent Results ({results.length})
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Status</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Amount</TableCell>
                    <TableCell>Time</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.slice(-10).reverse().map((result, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Chip
                          icon={getStatusIcon(result.status)}
                          label={result.status.replace('_', ' ')}
                          color={getStatusColor(result.status) as any}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap>
                          {result.message}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {result.offer_amount && `$${result.offer_amount}`}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatTimestamp(result.timestamp)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          onClick={() => setSelectedResult(result)}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Listings Modal */}
      <Dialog
        open={showListingsModal}
        onClose={closeModal}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { 
            height: '80vh',
            background: 'linear-gradient(135deg, rgba(25,118,210,0.1) 0%, rgba(156,39,176,0.1) 100%)',
            backdropFilter: 'blur(10px)',
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box display="flex" alignItems="center" gap={2}>
            <Search color="primary" />
            <Typography variant="h5" fontWeight="600">Total Listings</Typography>
          </Box>
          <IconButton onClick={closeModal}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {modalLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <LinearProgress sx={{ width: '50%' }} />
            </Box>
          ) : (
            <TableContainer component={Paper} sx={{ maxHeight: '60vh', background: 'transparent' }}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold' }}>Item ID</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Product</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Listing ID</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Messaged</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Messaged At</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detailedData?.listings?.map((listing: any, index: number) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="500" sx={{ fontFamily: 'monospace' }}>
                          {listing.item_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {listing.product}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="primary.main" fontWeight="600">
                          #{listing.listing_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={listing.messaged ? 'Yes' : 'No'} 
                          color={listing.messaged ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {listing.messaged_at}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {listing.url && (
                          <IconButton 
                            size="small" 
                            onClick={() => window.open(listing.url, '_blank')}
                            sx={{ color: 'primary.main' }}
                          >
                            <OpenInNew fontSize="small" />
                          </IconButton>
                        )}
                      </TableCell>
                    </TableRow>
                  )) || (
                    <TableRow>
                      <TableCell colSpan={6} align="center">
                        <Typography variant="body2" color="text.secondary">
                          No listings data available
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
      </Dialog>

      {/* Offers Modal */}
      <Dialog
        open={showOffersModal}
        onClose={closeModal}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { 
            height: '80vh',
            background: 'linear-gradient(135deg, rgba(76,175,80,0.1) 0%, rgba(56,142,60,0.1) 100%)',
            backdropFilter: 'blur(10px)',
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box display="flex" alignItems="center" gap={2}>
            <AttachMoney color="primary" />
            <Typography variant="h5" fontWeight="600">Offers Sent</Typography>
          </Box>
          <IconButton onClick={closeModal}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {modalLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <LinearProgress sx={{ width: '50%' }} />
            </Box>
          ) : (
            <TableContainer component={Paper} sx={{ maxHeight: '60vh', background: 'transparent' }}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold' }}>Item ID</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Product</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Listing ID</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Messaged At</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detailedData?.offers?.map((offer: any, index: number) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="500" sx={{ fontFamily: 'monospace' }}>
                          {offer.item_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {offer.product}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="primary.main" fontWeight="600">
                          #{offer.listing_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {offer.messaged_at}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {offer.url && (
                          <IconButton 
                            size="small" 
                            onClick={() => window.open(offer.url, '_blank')}
                            sx={{ color: 'primary.main' }}
                          >
                            <OpenInNew fontSize="small" />
                          </IconButton>
                        )}
                      </TableCell>
                    </TableRow>
                  )) || (
                    <TableRow>
                      <TableCell colSpan={5} align="center">
                        <Typography variant="body2" color="text.secondary">
                          No offers data available
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
      </Dialog>

      {/* Active Negotiations Modal */}
      <Dialog
        open={showNegotiationsModal}
        onClose={closeModal}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { 
            height: '80vh',
            background: 'linear-gradient(135deg, rgba(255,152,0,0.1) 0%, rgba(245,124,0,0.1) 100%)',
            backdropFilter: 'blur(10px)',
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box display="flex" alignItems="center" gap={2}>
            <Chat color="primary" />
            <Typography variant="h5" fontWeight="600">Active Negotiations</Typography>
          </Box>
          <IconButton onClick={closeModal}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {modalLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <LinearProgress sx={{ width: '50%' }} />
            </Box>
          ) : (
            <TableContainer component={Paper} sx={{ maxHeight: '60vh', background: 'transparent' }}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold' }}>Message ID</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Last Message</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>From</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Messages</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Counter Offer</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Updated</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detailedData?.negotiations?.map((negotiation: any, index: number) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="500" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                          {negotiation.message_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={negotiation.status} 
                          color={negotiation.status === 'Deal Pending' ? 'success' : 
                                 negotiation.status === 'Negotiating' ? 'warning' : 'info'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 180, fontSize: '0.85rem' }}>
                          {negotiation.last_message}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={negotiation.last_from} 
                          color={negotiation.last_from === 'You' ? 'info' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="primary.main" fontWeight="600">
                          {negotiation.message_count}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="success.main" fontWeight="600">
                          {negotiation.counter_offer}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                          {negotiation.last_updated}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {negotiation.conversation_url && (
                          <IconButton 
                            size="small" 
                            onClick={() => window.open(negotiation.conversation_url, '_blank')}
                            sx={{ color: 'primary.main' }}
                          >
                            <OpenInNew fontSize="small" />
                          </IconButton>
                        )}
                      </TableCell>
                    </TableRow>
                  )) || (
                    <TableRow>
                      <TableCell colSpan={8} align="center">
                        <Typography variant="body2" color="text.secondary">
                          No active negotiations
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
      </Dialog>

      {/* Result Detail Dialog */}
      <Dialog
        open={!!selectedResult}
        onClose={() => setSelectedResult(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Result Details
        </DialogTitle>
        <DialogContent>
          {selectedResult && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Status: {selectedResult.status.replace('_', ' ')}
              </Typography>
              <Typography variant="body1" paragraph>
                {selectedResult.message}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                URL: {selectedResult.url}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Time: {formatTimestamp(selectedResult.timestamp)}
              </Typography>
              {selectedResult.offer_amount && (
                <Typography variant="body2" color="text.secondary">
                  Offer Amount: ${selectedResult.offer_amount}
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedResult(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AutomationDashboard;