import React, { useState, useEffect, useMemo } from 'react';
import { format } from 'date-fns';
import { getApiBaseUrl } from './config';
import _ from 'lodash';

const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-blue-600 rounded-full border-t-transparent"></div>
);

const Dashboard = () => {
  // State management
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [debouncedFilter, setDebouncedFilter] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selectedSources, setSelectedSources] = useState(new Set());
  const [isFiltering, setIsFiltering] = useState(false);
  const [filteredProperties, setFilteredProperties] = useState([]);

  useEffect(() => {
    fetchProperties();
  }, []);

  // API calls
  const fetchProperties = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Fetching properties...');
      const response = await fetch(`${getApiBaseUrl()}/properties`);
      if (!response.ok) throw new Error('Failed to fetch properties');
      const data = await response.json();
      console.log('Received properties: ', data.length);
      setProperties(data);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching properties:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const exportData = async () => {
    try {
      console.log('Starting export with filtered properties:', filteredProperties);
      // Define column order to match dashboard
      const columnOrder = [
        'Property',
        'Address',
        'Floor/Suite',
        'Space (sq ft)',
        'Price',
        'Source',
        'Listing URL',
        'Last Updated'
      ];

      // Log a sample property to see field names
      if (filteredProperties.length > 0) {
        console.log('Sample property fields:', Object.keys(filteredProperties[0]));
        console.log('Sample property data:', filteredProperties[0]);
      }

      // Format the data to match the dashboard display
      const formattedProperties = filteredProperties.map(p => {
        const formatted = {
          Property: p.property_name || 'N/A',
          Address: p.address || 'N/A',
          'Floor/Suite': p.floor_suite || 'N/A',
          'Space (sq ft)': p.space_available || 'N/A',
          Price: p.price || 'N/A',
          Source: p.source || 'N/A',
          'Listing URL': p.listing_url || 'N/A',
          'Last Updated': p.updated_at ? format(new Date(p.updated_at), 'MMM d, yyyy HH:mm:ss') : 'N/A'
        };
        // Return object with properties in the correct order
        return columnOrder.reduce((obj, key) => ({ ...obj, [key]: formatted[key] }), {});
      });

      console.log('Making export request to:', `${getApiBaseUrl()}/export`);
      const requestData = { properties: formattedProperties };
      console.log('Request data:', requestData);
      
      const response = await fetch(`${getApiBaseUrl()}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
      });
      
      console.log('Export response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Export error:', errorText);
        throw new Error(`Failed to export data: ${errorText}`);
      }
      
      const blob = await response.blob();
      console.log('Received blob:', blob);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'properties.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting data:', err);
    }
  };

  // Get unique sources
  const sources = useMemo(() => {
    const sourceSet = new Set(properties.map(p => p.source));
    return Array.from(sourceSet).sort();
  }, [properties]);

  // Initialize selected sources when properties change
  useEffect(() => {
    if (selectedSources.size === 0 && sources.length > 0) {
      setSelectedSources(new Set(sources));
    }
  }, [sources]);

  // Debounced filter computation
  const debouncedCompute = useMemo(
    () => _.debounce((searchProps, searchTerm, sources) => {
      const filtered = searchProps.filter(property => {
        const matchesSearch = searchTerm === '' || [
          property.property_name,
          property.address,
          property.floor_suite,
          property.space_available,
          property.price,
          property.source,
          property.listing_url
        ].some(field => field?.toString().toLowerCase().includes(searchTerm));
        
        const matchesSource = sources.has(property.source);
        return matchesSearch && matchesSource;
      });
      setFilteredProperties(filtered);
      setIsFiltering(false);
    }, 100),
    []
  );

  // Debounced search handler
  const debouncedSetFilter = useMemo(
    () => _.debounce((value) => setDebouncedFilter(value), 300),
    []
  );

  // Update debounced filter
  useEffect(() => {
    debouncedSetFilter(filter);
  }, [filter]);

  // Compute filtered results when dependencies change
  useEffect(() => {
    setIsFiltering(true);
    debouncedCompute(properties, debouncedFilter.toLowerCase(), selectedSources);
    return () => debouncedCompute.cancel();
  }, [properties, debouncedFilter, selectedSources]);

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Property Listings Dashboard</h1>
              <p className="text-sm text-gray-500 mt-1">
                {properties.length} properties • Last updated: {lastUpdated ? format(lastUpdated, 'MMM d, yyyy HH:mm:ss') : 'Never'}
              </p>
            </div>
            <div className="flex gap-4">
              <button
                onClick={fetchProperties}
                className={`px-4 py-2 rounded-md text-white ${loading ? 'bg-blue-400' : 'bg-blue-600 hover:bg-blue-700'}`}
                disabled={loading}
              >
                {loading ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                onClick={exportData}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md"
              >
                Export CSV
              </button>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-8">
            <div className="flex">
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="mb-6 space-y-4">
          <input
            type="text"
            placeholder="Search properties by name or address..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-4 py-2 rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={selectedSources.size === sources.length}
                onChange={(e) => {
                  if (e.target.checked) {
                    // Check all
                    setSelectedSources(new Set(sources));
                  } else {
                    // Uncheck all
                    setSelectedSources(new Set());
                  }
                }}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-900">All</span>
            </label>
            {sources.map(source => (
              <label key={source} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={selectedSources.has(source)}
                  onChange={(e) => {
                    const newSources = new Set(selectedSources);
                    if (e.target.checked) {
                      newSources.add(source);
                    } else {
                      newSources.delete(source);
                    }
                    setSelectedSources(newSources);
                  }}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">{source}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Property count */}
        <div className="mb-4">
          <span className="text-lg font-semibold text-gray-700">{filteredProperties.length.toLocaleString()} Spaces</span>
        </div>

        {/* Properties table */}
        <div className="bg-white rounded-lg shadow overflow-hidden max-w-fit relative">
          {/* Loading overlay */}
          {isFiltering && (
            <div className="absolute inset-0 bg-white/80 flex items-center justify-center z-10">
              <Spinner />
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="divide-y divide-gray-200 table-fixed w-fit">
              <thead className="bg-gray-50">
                <tr>
                  <th className="w-80 max-w-[20rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Property</th>
                  <th className="w-80 max-w-[20rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Address</th>
                  <th className="w-40 max-w-[10rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Floor</th>
                  <th className="w-20 max-w-[5rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Space</th>
                  <th className="w-24 max-w-[6rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Price</th>
                  <th className="w-24 max-w-[6rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Source</th>
                  <th className="w-16 max-w-[4rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Link</th>
                  <th className="w-48 max-w-[12rem] px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-hidden">Updated</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredProperties.map(property => (
                  <tr key={property.id} className="hover:bg-gray-50">
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-900 truncate overflow-hidden">{property.property_name || 'N/A'}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-500 truncate overflow-hidden">{property.address}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-500 truncate overflow-hidden">{property.floor_suite || 'N/A'}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-500 truncate overflow-hidden">{property.space_available || 'N/A'}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-900 truncate overflow-hidden">{property.price}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-500 truncate overflow-hidden">{property.source}</td>
                    <td className="w-16 max-w-[4rem] px-2 py-1 text-xs text-gray-500 truncate overflow-hidden">
                      {property.listing_url ? (
                        <a 
                          href={property.listing_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          View
                        </a>
                      ) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {property.updated_at ? format(new Date(property.updated_at), 'MMM d, yyyy HH:mm:ss') : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
