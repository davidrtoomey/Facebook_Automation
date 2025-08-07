import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
  Card,
  CardContent,
  Switch,
  FormControlLabel,
  Chip,
  InputAdornment,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Slider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
} from '@mui/material';
import {
  Settings,
  ExpandMore,
  Add,
  Delete,
  AttachMoney,
  Speed,
  Security,
  Science,
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

interface ConfigurationFormProps {
  initialConfig?: any;
  onConfigurationSaved: (config: any) => void;
  onError: (error: string) => void;
}

const ConfigurationForm: React.FC<ConfigurationFormProps> = ({
  initialConfig,
  onConfigurationSaved,
  onError,
}) => {
  const [config, setConfig] = useState({
    gemini_api_key: '',
    notification_email: '',
    search_products: [
      {
        name: 'iPhone 13 Pro Max',
        base_offer_unlocked: 300,
        base_offer_locked: 250,
        base_offer_unlocked_damaged: 150,
        base_offer_locked_damaged: 100,
      }
    ],
    search_keywords: [] as string[],
    price_flexibility: 20,
    max_conversations: 10,
    max_offers_per_run: 5,
    browser_headless: false,
    browser_delay: 2,
    strategy: 'primary',
    enable_negotiation: true,
  });

  const [newProduct, setNewProduct] = useState('');
  const [newKeyword, setNewKeyword] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [validationError, setValidationError] = useState('');
  
  // Negotiation Script Management
  const [negotiationScript, setNegotiationScript] = useState('');
  const [isEditingScript, setIsEditingScript] = useState(false);
  const [isSavingScript, setIsSavingScript] = useState(false);
  
  // Meetup Location Management
  const [meetupLocation, setMeetupLocation] = useState('');
  const [isEditingLocation, setIsEditingLocation] = useState(false);
  const [isSavingLocation, setIsSavingLocation] = useState(false);

  useEffect(() => {
    if (initialConfig) {
      console.log('[CONFIG DEBUG] Loading initialConfig:', {
        notification_email: initialConfig.notification_email,
        hasNotificationEmail: !!initialConfig.notification_email
      });
      setConfig(prevConfig => ({
        ...prevConfig,
        ...initialConfig,
      }));
    }
  }, [initialConfig]);

  // Load negotiation script and meetup location on component mount
  useEffect(() => {
    const loadScriptAndLocation = async () => {
      try {
        const [scriptResponse, locationResponse] = await Promise.all([
          ApiService.getNegotiationScript(),
          ApiService.getMeetupLocation()
        ]);
        
        setNegotiationScript(scriptResponse.content || '');
        setMeetupLocation(locationResponse.location || '');
      } catch (error) {
        console.error('Failed to load negotiation script or meetup location:', error);
      }
    };

    loadScriptAndLocation();
  }, []);

  const handleInputChange = (field: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [field]: value,
    }));
    setValidationError('');
  };

  const addProduct = () => {
    if (newProduct.trim() && !config.search_products.find(p => p.name === newProduct.trim())) {
      setConfig(prev => ({
        ...prev,
        search_products: [...prev.search_products, {
          name: newProduct.trim(),
          base_offer_unlocked: 300,
          base_offer_locked: 250,
          base_offer_unlocked_damaged: 150,
          base_offer_locked_damaged: 100,
        }],
      }));
      setNewProduct('');
    }
  };

  const removeProduct = (productToRemove: string) => {
    setConfig(prev => ({
      ...prev,
      search_products: prev.search_products.filter(p => p.name !== productToRemove),
    }));
  };

  const updateProductPricing = (productName: string, field: string, value: number) => {
    setConfig(prev => ({
      ...prev,
      search_products: prev.search_products.map(product =>
        product.name === productName
          ? { ...product, [field]: value }
          : product
      ),
    }));
  };

  const addKeyword = () => {
    if (newKeyword.trim() && !config.search_keywords.includes(newKeyword.trim())) {
      setConfig(prev => ({
        ...prev,
        search_keywords: [...prev.search_keywords, newKeyword.trim()],
      }));
      setNewKeyword('');
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    setConfig(prev => ({
      ...prev,
      search_keywords: prev.search_keywords.filter(k => k !== keywordToRemove),
    }));
  };

  const handleTestConfiguration = async () => {
    setIsTesting(true);
    setTestResult(null);
    
    try {
      const result = await ApiService.testConfiguration(config);
      setTestResult(result);
    } catch (error) {
      setTestResult({
        valid: false,
        message: `Test failed: ${error}`,
        details: {}
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveNegotiationScript = async () => {
    setIsSavingScript(true);
    try {
      await ApiService.saveNegotiationScript(negotiationScript);
      setIsEditingScript(false);
      onConfigurationSaved({ ...config }); // Trigger a success message
    } catch (error) {
      onError(`Failed to save negotiation script: ${error}`);
    } finally {
      setIsSavingScript(false);
    }
  };

  const handleSaveMeetupLocation = async () => {
    setIsSavingLocation(true);
    try {
      await ApiService.saveMeetupLocation(meetupLocation);
      setIsEditingLocation(false);
      onConfigurationSaved({ ...config }); // Trigger a success message
    } catch (error) {
      onError(`Failed to save meetup location: ${error}`);
    } finally {
      setIsSavingLocation(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!config.gemini_api_key.trim()) {
      setValidationError('Gemini API key is required');
      return;
    }

    if (config.search_products.length === 0) {
      setValidationError('At least one search product is required');
      return;
    }

    setIsSaving(true);
    setValidationError('');

    try {
      await ApiService.saveConfiguration(config);
      onConfigurationSaved(config);
    } catch (error) {
      setValidationError(`Failed to save configuration: ${error}`);
      onError(`Failed to save configuration: ${error}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Box maxWidth={800} mx="auto">
      <Box textAlign="center" mb={4}>
        <Settings sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
        <Typography variant="h4" gutterBottom>
          Configuration
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure your automation settings and API credentials
        </Typography>
      </Box>

      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          {/* API Configuration */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <Security />
                  <Typography variant="h6">
                    API Configuration
                  </Typography>
                </Box>
                <TextField
                  fullWidth
                  label="Gemini API Key"
                  type="password"
                  value={config.gemini_api_key}
                  onChange={(e) => handleInputChange('gemini_api_key', e.target.value)}
                  required
                  error={!!validationError}
                  helperText={validationError || 'Your Gemini API key for AI processing'}
                  sx={{ mb: 3 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Security />
                      </InputAdornment>
                    ),
                  }}
                />
                
                <TextField
                  fullWidth
                  label="Notification Email"
                  type="email"
                  value={config.notification_email}
                  onChange={(e) => handleInputChange('notification_email', e.target.value)}
                  helperText={
                    config.notification_email.trim() 
                      ? `✅ Notifications will be sent to: ${config.notification_email}`
                      : "Email address to receive notifications when agent needs help or deals close"
                  }
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        {config.notification_email.trim() ? '✅' : '📧'}
                      </InputAdornment>
                    ),
                  }}
                />
              </CardContent>
            </Card>
          </Grid>

          {/* Search Configuration */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Search Configuration
                </Typography>
                
                <Box mb={3}>
                  <Typography variant="subtitle1" gutterBottom>
                    Search Products
                  </Typography>
                  <Box display="flex" gap={1} mb={2}>
                    <TextField
                      fullWidth
                      label="Add Product"
                      value={newProduct}
                      onChange={(e) => setNewProduct(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && addProduct()}
                      placeholder="e.g., iPhone 14 Pro"
                    />
                    <Button
                      variant="outlined"
                      onClick={addProduct}
                      startIcon={<Add />}
                      disabled={!newProduct.trim()}
                    >
                      Add
                    </Button>
                  </Box>
                  <Box display="flex" flexWrap="wrap" gap={1}>
                    {config.search_products.map((product) => (
                      <Chip
                        key={product.name}
                        label={product.name}
                        onDelete={() => removeProduct(product.name)}
                        deleteIcon={<Delete />}
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>

                <Box>
                  <Typography variant="subtitle1" gutterBottom>
                    Additional Keywords (Optional)
                  </Typography>
                  <Box display="flex" gap={1} mb={2}>
                    <TextField
                      fullWidth
                      label="Add Keyword"
                      value={newKeyword}
                      onChange={(e) => setNewKeyword(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && addKeyword()}
                      placeholder="e.g., unlocked, pristine"
                    />
                    <Button
                      variant="outlined"
                      onClick={addKeyword}
                      startIcon={<Add />}
                      disabled={!newKeyword.trim()}
                    >
                      Add
                    </Button>
                  </Box>
                  <Box display="flex" flexWrap="wrap" gap={1}>
                    {config.search_keywords.map((keyword) => (
                      <Chip
                        key={keyword}
                        label={keyword}
                        onDelete={() => removeKeyword(keyword)}
                        deleteIcon={<Delete />}
                        variant="outlined"
                        size="small"
                      />
                    ))}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Pricing Configuration */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <AttachMoney />
                  <Typography variant="h6">
                    Pricing Configuration
                  </Typography>
                </Box>
                
{config.search_products.map((product, index) => (
                  <Card key={product.name} variant="outlined" sx={{ mb: 2 }}>
                    <CardContent>
                      <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
                        {product.name} - Pricing Configuration
                      </Typography>
                      
                      <Grid container spacing={3}>
                        <Grid item xs={12}>
                          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                            Good Condition Phones
                          </Typography>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <TextField
                            fullWidth
                            label="Base Offer - Unlocked (Good)"
                            type="number"
                            value={product.base_offer_unlocked}
                            onChange={(e) => updateProductPricing(product.name, 'base_offer_unlocked', parseInt(e.target.value))}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                            helperText="Default offer for unlocked devices in good condition"
                          />
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <TextField
                            fullWidth
                            label="Base Offer - Locked (Good)"
                            type="number"
                            value={product.base_offer_locked}
                            onChange={(e) => updateProductPricing(product.name, 'base_offer_locked', parseInt(e.target.value))}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                            helperText="Default offer for locked devices in good condition"
                          />
                        </Grid>
                        
                        <Grid item xs={12}>
                          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold', color: 'warning.main', mt: 2 }}>
                            Damaged/Cracked/Bad LCD Phones
                          </Typography>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <TextField
                            fullWidth
                            label="Base Offer - Unlocked (Damaged)"
                            type="number"
                            value={product.base_offer_unlocked_damaged}
                            onChange={(e) => updateProductPricing(product.name, 'base_offer_unlocked_damaged', parseInt(e.target.value))}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                            helperText="Default offer for unlocked devices with damage"
                          />
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <TextField
                            fullWidth
                            label="Base Offer - Locked (Damaged)"
                            type="number"
                            value={product.base_offer_locked_damaged}
                            onChange={(e) => updateProductPricing(product.name, 'base_offer_locked_damaged', parseInt(e.target.value))}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                            helperText="Default offer for locked devices with damage"
                          />
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                ))}
                
                <Box mt={3}>
                  <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
                    Global Pricing Settings
                  </Typography>
                  <Typography gutterBottom>
                    Price Flexibility: ${config.price_flexibility}
                  </Typography>
                  <Slider
                    value={config.price_flexibility}
                    onChange={(_, value) => handleInputChange('price_flexibility', value)}
                    min={0}
                    max={50}
                    step={5}
                    marks
                    valueLabelDisplay="auto"
                    valueLabelFormat={(value) => `$${value}`}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Advanced Settings */}
          <Grid item xs={12}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">Advanced Settings</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Max Conversations"
                      type="number"
                      value={config.max_conversations}
                      onChange={(e) => handleInputChange('max_conversations', parseInt(e.target.value))}
                      helperText="Maximum conversations per run"
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Max Offers per Run"
                      type="number"
                      value={config.max_offers_per_run}
                      onChange={(e) => handleInputChange('max_offers_per_run', parseInt(e.target.value))}
                      helperText="Maximum offers to send per run"
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <FormControl fullWidth>
                      <InputLabel>Strategy</InputLabel>
                      <Select
                        value={config.strategy}
                        label="Strategy"
                        onChange={(e) => handleInputChange('strategy', e.target.value)}
                      >
                        <MenuItem value="primary">Primary</MenuItem>
                        <MenuItem value="aggressive">Aggressive</MenuItem>
                        <MenuItem value="conservative">Conservative</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Browser Delay (seconds)"
                      type="number"
                      value={config.browser_delay}
                      onChange={(e) => handleInputChange('browser_delay', parseInt(e.target.value))}
                      helperText="Delay between browser actions"
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.browser_headless}
                          onChange={(e) => handleInputChange('browser_headless', e.target.checked)}
                        />
                      }
                      label="Run Browser in Headless Mode"
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.enable_negotiation}
                          onChange={(e) => handleInputChange('enable_negotiation', e.target.checked)}
                        />
                      }
                      label="Enable Automatic Negotiation"
                    />
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          </Grid>

          {/* Test Configuration */}
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Science />
                    <Typography variant="h6">
                      Test Configuration
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    onClick={handleTestConfiguration}
                    disabled={isTesting}
                    startIcon={isTesting ? <CircularProgress size={20} /> : <Science />}
                  >
                    {isTesting ? 'Testing...' : 'Test Configuration'}
                  </Button>
                </Box>
                
                {testResult && (
                  <Alert severity={testResult.valid ? 'success' : 'error'}>
                    <Typography variant="body2">
                      <strong>{testResult.message}</strong>
                    </Typography>
                    {testResult.details && Object.keys(testResult.details).length > 0 && (
                      <Box mt={1}>
                        {Object.entries(testResult.details).map(([key, value]) => (
                          <Typography key={key} variant="body2">
                            • {key}: {value ? '✓' : '✗'}
                          </Typography>
                        ))}
                      </Box>
                    )}
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Negotiation Script */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Science />
                    <Typography variant="h6">Negotiation Script</Typography>
                  </Box>
                  <Box display="flex" gap={1}>
                    {!isEditingScript ? (
                      <>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => setIsEditingScript(true)}
                        >
                          Edit
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="contained"
                          size="small"
                          onClick={handleSaveNegotiationScript}
                          disabled={isSavingScript}
                        >
                          {isSavingScript ? 'Saving...' : 'Save'}
                        </Button>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => setIsEditingScript(false)}
                          disabled={isSavingScript}
                        >
                          Cancel
                        </Button>
                      </>
                    )}
                  </Box>
                </Box>
                <TextField
                  fullWidth
                  multiline
                  rows={15}
                  value={negotiationScript}
                  onChange={(e) => setNegotiationScript(e.target.value)}
                  disabled={!isEditingScript}
                  placeholder="Negotiation script content will appear here..."
                  variant={isEditingScript ? "outlined" : "filled"}
                  sx={{
                    '& .MuiInputBase-input': {
                      fontFamily: 'monospace',
                      fontSize: '0.875rem',
                    }
                  }}
                />
              </CardContent>
            </Card>
          </Grid>

          {/* Meetup Location */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <AttachMoney />
                    <Typography variant="h6">Meetup Location</Typography>
                  </Box>
                  <Box display="flex" gap={1}>
                    {!isEditingLocation ? (
                      <>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => setIsEditingLocation(true)}
                        >
                          Edit
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="contained"
                          size="small"
                          onClick={handleSaveMeetupLocation}
                          disabled={isSavingLocation}
                        >
                          {isSavingLocation ? 'Saving...' : 'Save'}
                        </Button>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => setIsEditingLocation(false)}
                          disabled={isSavingLocation}
                        >
                          Cancel
                        </Button>
                      </>
                    )}
                  </Box>
                </Box>
                <TextField
                  fullWidth
                  value={meetupLocation}
                  onChange={(e) => setMeetupLocation(e.target.value)}
                  disabled={!isEditingLocation}
                  placeholder="Enter your preferred meetup location address..."
                  variant={isEditingLocation ? "outlined" : "filled"}
                  helperText="This location will be used in all negotiation conversations"
                />
              </CardContent>
            </Card>
          </Grid>

          {/* Save Configuration */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2 }} />
            <Box display="flex" justifyContent="flex-end" gap={2}>
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={isSaving}
                startIcon={isSaving ? <CircularProgress size={20} /> : <Settings />}
              >
                {isSaving ? 'Saving...' : 'Save Configuration'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </form>
    </Box>
  );
};

export default ConfigurationForm;