import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { RefreshCw, Download, Search, Building, DollarSign, MapPin, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';

const PropertyDashboard = () => {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [selectedScraper, setSelectedScraper] = useState('cbre');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [changes, setChanges] = useState({ new: [], modified: [], removed: [] });

  import { getApiBaseUrl } from './config';

const API_BASE_URL = getApiBaseUrl();

const fetchData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/properties?source=${selectedScraper}`);
      const { status, data, message } = await response.json();
      
      if (status === 'error') {
        setError(message);
        return;
      }
      
      setProperties(data);
      setLastUpdated(new Date());
      
      // Get changes since last scrape
      const changesResponse = await fetch(`${API_BASE_URL}/changes?source=${selectedScraper}`);
      const changesData = await changesResponse.json();
      setChanges(changesData);
    } catch (err) {
      setError('Failed to fetch property data');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [selectedScraper]);

  const triggerScrape = async () => {
    try {
      setLoading(true);
      await fetch(`${API_BASE_URL}/scrapers/${selectedScraper}/run`, { method: 'POST' });
      setTimeout(fetchData, 2000);
    } catch (err) {
      setError('Failed to trigger scrape');
    } finally {
      setLoading(false);
    }
  };

  const exportToCsv = async () => {
    try {
      window.location.href = `${API_BASE_URL}/export?source=${selectedScraper}`;
    } catch (err) {
      setError('Failed to export data');
    }
  };

  // Sort properties by created_at date
  const sortedProperties = [...properties].sort((a, b) => {
    return new Date(b.created_at) - new Date(a.created_at);
  });

  const filteredProperties = sortedProperties.filter(property => 
    property.property_name.toLowerCase().includes(filter.toLowerCase()) ||
    property.address.toLowerCase().includes(filter.toLowerCase()) ||
    property.floor_suite.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header Section */}
      <div className="mb-6 space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">Property Listings Dashboard</h1>
            <p className="text-sm text-gray-500">
              {properties.length} properties • Last updated: {lastUpdated ? format(lastUpdated, 'MMM d, yyyy HH:mm:ss') : 'Never'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={exportToCsv}
              variant="outline"
              className="flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </Button>
            <Button
              onClick={triggerScrape}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Scraping...' : 'Run Scraper'}
            </Button>
          </div>
        </div>

        {/* Changes Summary */}
        {(changes.new.length > 0 || changes.modified.length > 0 || changes.removed.length > 0) && (
          <Alert className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Recent Changes</AlertTitle>
            <AlertDescription>
              <div className="flex gap-4 mt-2">
                {changes.new.length > 0 && (
                  <span className="text-green-600">{changes.new.length} new listings</span>
                )}
                {changes.modified.length > 0 && (
                  <span className="text-blue-600">{changes.modified.length} modified listings</span>
                )}
                {changes.removed.length > 0 && (
                  <span className="text-red-600">{changes.removed.length} removed listings</span>
                )}
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Filter Section */}
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-500" />
            <Input
              placeholder="Filter properties..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={selectedScraper} onValueChange={setSelectedScraper}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Select source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cbre">CBRE</SelectItem>
              {/* Add other scrapers here */}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Properties Table */}
      <div className="bg-white rounded-lg shadow">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[300px]">Property</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Space</TableHead>
              <TableHead>Price</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredProperties.map((property, index) => (
              <TableRow 
                key={`${property.property_name}-${index}`}
                className={
                  property._status === 'new' ? 'bg-green-50' :
                  property._status === 'modified' ? 'bg-blue-50' :
                  property._status === 'removed' ? 'bg-red-50' : ''
                }
              >
                <TableCell className="font-medium">
                  <div className="flex items-start gap-2">
                    <Building className="w-4 h-4 mt-1 flex-shrink-0" />
                    <div>
                      <div className="flex items-center gap-2">
                        {property.property_name}
                        {property._status === 'new' && (
                          <span className="px-2 py-1 text-xs font-semibold text-green-800 bg-green-100 rounded-full">New</span>
                        )}
                        {property._status === 'modified' && (
                          <span className="px-2 py-1 text-xs font-semibold text-blue-800 bg-blue-100 rounded-full">Updated</span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">{property.floor_suite}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-start gap-2">
                    <MapPin className="w-4 h-4 mt-1 flex-shrink-0" />
                    <span>{property.address}</span>
                  </div>
                </TableCell>
                <TableCell>{property.space_available}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    {property.price || 'Contact for pricing'}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(property.listing_url, '_blank')}
                  >
                    View Listing
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default PropertyDashboard;