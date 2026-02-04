interface FileListData {
    files: File[];
    names: string[];
}

interface FileInfo {
    file: File;
    name: string;
    nmi?: string;
    reportName?: string;
    dateRange?: string;
    eventType?: 'BEFORE' | 'AFTER';
}

interface FilePair {
    before: FileInfo;
    after: FileInfo;
    id: string;
    enabled: boolean;
}

interface ComparisonResult {
    metadata: {
        reportName: string;
        reportDate: string;
        reportTime: string;
        beforeReport: string;
        afterReport: string;
    };
    details: Array<{
        sr: number;
        issue_type: string;
        nmi: string;
        record_type: string;
        channel: string;
        date: string;
        field_name: string;
        after_cell_location: string;
        before_value: string;
        after_value: string;
        details: string;
    }>;
}

interface PairComparisonResult {
    pair: FilePair;
    result: ComparisonResult;
}

class Nem12ComparisonUI {
    private beforeFiles: FileListData = { files: [], names: [] };
    private afterFiles: FileListData = { files: [], names: [] };
    private beforeFileInfos: FileInfo[] = [];
    private afterFileInfos: FileInfo[] = [];
    private filePairs: FilePair[] = [];
    private pairResults: PairComparisonResult[] = [];
    private activeTab: string | null = null;
    private results: ComparisonResult | null = null;
    private currentDetails: ComparisonResult['details'] = []; // Store current filtered/sorted details
    private sortColumn: number | null = null;
    private sortDirection: 'asc' | 'desc' = 'asc';
    private searchHandler?: (e: Event) => void;
    private resetHandler?: () => void;
    private exportHandler?: () => void;

    constructor() {
        this.initializeEventListeners();
        // Expose togglePair globally for inline event handlers
        (window as any).nem12UI = this;
        // Expose resetPage for button
        (window as any).resetPage = () => this.resetPage();
    }

    private initializeEventListeners(): void {
        const fileInput = document.getElementById('fileInput') as HTMLInputElement;
        const compareBtn = document.getElementById('compareBtn') as HTMLButtonElement;
        const closeBtn = document.getElementById('closeBtn') as HTMLButtonElement;
        const selectAllBtn = document.getElementById('selectAllBtn') as HTMLButtonElement;
        const deselectAllBtn = document.getElementById('deselectAllBtn') as HTMLButtonElement;

        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }

        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.handleCompare());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                if (confirm('Are you sure you want to close?')) {
                    window.close();
                }
            });
        }

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this.selectAllPairs(true));
        }

        if (deselectAllBtn) {
            deselectAllBtn.addEventListener('click', () => this.selectAllPairs(false));
        }
    }

    private parseFileName(filename: string): Partial<FileInfo> {
        // Pattern: ReportName_NMI_FromDate-ToDate_EventType.ext
        // Example: Utopia_Electricity_CET_AE69008084_20251101-20251201_BEFORE.csv
        
        const info: Partial<FileInfo> = { name: filename };
        
        // Remove extension
        const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
        const parts = nameWithoutExt.split('_');
        
        if (parts.length >= 4) {
            // Last part is event type
            const lastPart = parts[parts.length - 1].toUpperCase();
            if (lastPart === 'BEFORE' || lastPart === 'AFTER') {
                info.eventType = lastPart as 'BEFORE' | 'AFTER';
            }
            
            // Second to last part might be date range (YYYYMMDD-YYYYMMDD)
            const datePart = parts[parts.length - 2];
            if (datePart.includes('-') && datePart.length >= 15) {
                info.dateRange = datePart;
            }
            
            // Find NMI (usually alphanumeric, 10-11 chars, after report name)
            // NMI is typically the part before date range
            const nmiIndex = parts.length - (info.dateRange ? 3 : 2);
            if (nmiIndex >= 0 && parts[nmiIndex]) {
                const potentialNMI = parts[nmiIndex];
                // NMI is usually 10-11 alphanumeric characters
                if (/^[A-Z0-9]{8,12}$/i.test(potentialNMI)) {
                    info.nmi = potentialNMI;
                }
            }
            
            // Report name is everything before NMI
            if (info.nmi) {
                const nmiIdx = parts.indexOf(info.nmi);
                if (nmiIdx > 0) {
                    info.reportName = parts.slice(0, nmiIdx).join('_');
                }
            } else {
                // Fallback: assume first parts are report name
                const reportNameEnd = parts.length - (info.dateRange ? 3 : 2);
                if (reportNameEnd > 0) {
                    info.reportName = parts.slice(0, reportNameEnd).join('_');
                }
            }
        }
        
        return info;
    }

    private handleFileSelection(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (!input.files || input.files.length === 0) return;

        try {
            const files = Array.from(input.files);
            
            // Parse and categorize files
            files.forEach(file => {
                const fileInfo: FileInfo = {
                    file: file,
                    name: file.name,
                    ...this.parseFileName(file.name)
                } as FileInfo;

                // Determine event type from filename or default
                if (!fileInfo.eventType) {
                    // Try to infer from filename
                    const nameUpper = file.name.toUpperCase();
                    if (nameUpper.includes('BEFORE')) {
                        fileInfo.eventType = 'BEFORE';
                    } else if (nameUpper.includes('AFTER')) {
                        fileInfo.eventType = 'AFTER';
                    } else {
                        // Default: ask user or categorize based on existing files
                        // For now, we'll try to match existing pairs
                        fileInfo.eventType = this.inferEventType(fileInfo);
                    }
                }

                // Add to appropriate list
                if (fileInfo.eventType === 'BEFORE') {
                    // Check if already exists
                    if (!this.beforeFileInfos.find(f => f.name === fileInfo.name)) {
                        this.beforeFileInfos.push(fileInfo);
                    }
                } else {
                    // Check if already exists
                    if (!this.afterFileInfos.find(f => f.name === fileInfo.name)) {
                        this.afterFileInfos.push(fileInfo);
                    }
                }
            });

            // Clear input to allow re-uploading same files
            input.value = '';

            // Match files first, then update display
            this.autoMatchFiles();
            this.updateFileMappingDisplay();
            this.updateCompareButtonState();
            this.updateUploadStatus(files.length);
            
            // Show warning if no pairs found
            if (this.filePairs.length === 0 && (this.beforeFileInfos.length > 0 || this.afterFileInfos.length > 0)) {
                console.warn('No file pairs matched. Files are matched by NMI, Report Name, and Date Range.');
            }
        } catch (error) {
            console.error('Error handling file selection:', error);
            alert('Error processing files. Please try again.');
        }
    }

    private inferEventType(fileInfo: FileInfo): 'BEFORE' | 'AFTER' {
        // If we have existing pairs, try to match
        // Otherwise, default to BEFORE if we have fewer before files
        if (this.beforeFileInfos.length <= this.afterFileInfos.length) {
            return 'BEFORE';
        }
        return 'AFTER';
    }

    private updateUploadStatus(count: number): void {
        const statusEl = document.getElementById('uploadStatus');
        if (statusEl) {
            if (count === 1) {
                statusEl.textContent = `${count} file added`;
            } else {
                statusEl.textContent = `${count} files added`;
            }
            statusEl.style.display = 'block';
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 3000);
        }
    }

    private updateFileMappingDisplay(): void {
        const mappingSection = document.getElementById('fileMappingSection');
        const mappingGridBody = document.getElementById('mappingGridBody');
        const compareSection = document.getElementById('compareSection');

        // Show/hide mapping section
        if (mappingSection) {
            mappingSection.style.display = (this.beforeFileInfos.length > 0 || this.afterFileInfos.length > 0) ? 'block' : 'none';
        }

        // Sort files for consistent display
        const sortedBeforeFiles = [...this.beforeFileInfos].sort((a, b) => {
            // Sort by report name, then NMI, then filename
            const nameA = (a.reportName || a.name).toLowerCase();
            const nameB = (b.reportName || b.name).toLowerCase();
            if (nameA !== nameB) return nameA.localeCompare(nameB);
            const nmiA = (a.nmi || '').toLowerCase();
            const nmiB = (b.nmi || '').toLowerCase();
            if (nmiA !== nmiB) return nmiA.localeCompare(nmiB);
            return a.name.localeCompare(b.name);
        });

        const sortedAfterFiles = [...this.afterFileInfos].sort((a, b) => {
            const nameA = (a.reportName || a.name).toLowerCase();
            const nameB = (b.reportName || b.name).toLowerCase();
            if (nameA !== nameB) return nameA.localeCompare(nameB);
            const nmiA = (a.nmi || '').toLowerCase();
            const nmiB = (b.nmi || '').toLowerCase();
            if (nmiA !== nmiB) return nmiA.localeCompare(nmiB);
            return a.name.localeCompare(b.name);
        });

        // Render grid format
        if (mappingGridBody) {
            if (this.filePairs.length === 0 && sortedBeforeFiles.length === 0 && sortedAfterFiles.length === 0) {
                mappingGridBody.innerHTML = '<div class="empty-grid-message">No files uploaded</div>';
            } else {
                // Create a map of pairs for quick lookup
                const pairMap = new Map<string, FilePair>();
                this.filePairs.forEach(pair => {
                    pairMap.set(pair.before.name, pair);
                });

                // Get all unique pairs and unmatched files
                const maxRows = Math.max(sortedBeforeFiles.length, sortedAfterFiles.length, this.filePairs.length);
                const rows: Array<{checkbox: string; before: string; after: string; isMatched?: boolean}> = [];

                // First, add all matched pairs (with matched class for green border)
                this.filePairs.forEach(pair => {
                    rows.push({
                        checkbox: `<input type="checkbox" class="pair-checkbox-grid" ${pair.enabled ? 'checked' : ''} 
                            data-pair-id="${pair.id}" onchange="window.nem12UI.togglePair('${pair.id}')">`,
                        before: this.formatFileDisplay(pair.before),
                        after: this.formatFileDisplay(pair.after),
                        isMatched: true
                    });
                });

                // Add unmatched before files
                sortedBeforeFiles.forEach(beforeFile => {
                    if (!pairMap.has(beforeFile.name)) {
                        rows.push({
                            checkbox: '<span class="no-checkbox">-</span>',
                            before: this.formatFileDisplay(beforeFile),
                            after: '<span class="unmatched-file">No match</span>',
                            isMatched: false
                        });
                    }
                });

                // Add unmatched after files
                sortedAfterFiles.forEach(afterFile => {
                    const isInPair = this.filePairs.some(p => p.after.name === afterFile.name);
                    if (!isInPair) {
                        rows.push({
                            checkbox: '<span class="no-checkbox">-</span>',
                            before: '<span class="unmatched-file">No match</span>',
                            after: this.formatFileDisplay(afterFile),
                            isMatched: false
                        });
                    }
                });

                // Sort rows by before file name for consistency
                rows.sort((a, b) => {
                    const beforeA = a.before.toLowerCase();
                    const beforeB = b.before.toLowerCase();
                    return beforeA.localeCompare(beforeB);
                });

                mappingGridBody.innerHTML = rows.map(row => `
                    <div class="mapping-grid-row ${row.isMatched ? 'matched-pair' : 'unmatched-pair'}">
                        <div class="grid-col-checkbox">${row.checkbox}</div>
                        <div class="grid-col-before">${row.before}</div>
                        <div class="grid-col-after">${row.after}</div>
                    </div>
                `).join('');
            }
        }

        // Show/hide compare button based on selected pairs
        if (compareSection) {
            const enabledPairs = this.filePairs.filter(p => p.enabled);
            compareSection.style.display = enabledPairs.length > 0 ? 'flex' : 'none';
        }
    }

    private formatFileDisplay(fileInfo: FileInfo): string {
        return `
            <div class="file-display-item">
                <div class="file-display-name">${this.escapeHtml(fileInfo.name)}</div>
            </div>
        `;
    }

    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    private truncateFileName(name: string, maxLength: number): string {
        if (name.length <= maxLength) return name;
        return name.substring(0, maxLength - 3) + '...';
    }

    private autoMatchFiles(): void {
        this.filePairs = [];
        const usedAfterFiles = new Set<string>();
        
        for (const beforeInfo of this.beforeFileInfos) {
            // Try to find matching after file by NMI and ReportName
            const match = this.afterFileInfos.find(afterInfo => {
                if (usedAfterFiles.has(afterInfo.name)) return false;
                const nmiMatch = beforeInfo.nmi && afterInfo.nmi && beforeInfo.nmi === afterInfo.nmi;
                const nameMatch = beforeInfo.reportName && afterInfo.reportName && 
                    beforeInfo.reportName.toLowerCase() === afterInfo.reportName.toLowerCase();
                const dateMatch = !beforeInfo.dateRange || !afterInfo.dateRange || 
                    beforeInfo.dateRange === afterInfo.dateRange;
                return nmiMatch && nameMatch && dateMatch;
            });

            if (match) {
                this.filePairs.push({
                    before: beforeInfo,
                    after: match,
                    id: `pair_${this.filePairs.length + 1}`,
                    enabled: true
                });
                usedAfterFiles.add(match.name);
            }
        }

        // Update file mapping display with connections
        this.updateFileMappingDisplay();
    }

    private selectAllPairs(select: boolean): void {
        this.filePairs.forEach(pair => {
            pair.enabled = select;
        });
        this.updateFileMappingDisplay();
        this.updateCompareButtonState();
    }

    private togglePair(pairId: string): void {
        const pair = this.filePairs.find(p => p.id === pairId);
        if (pair) {
            pair.enabled = !pair.enabled;
            this.updateFileMappingDisplay();
            this.updateCompareButtonState();
        }
    }

    private togglePairCollapse(pairId: string): void {
        const contentEl = document.getElementById(`content_${pairId}`);
        const toggleBtn = document.querySelector(`[data-pair-id="${pairId}"]`) as HTMLElement;
        const iconEl = toggleBtn?.querySelector('.collapse-icon');
        
        if (contentEl && toggleBtn && iconEl) {
            const isCollapsed = contentEl.style.display === 'none';
            contentEl.style.display = isCollapsed ? 'block' : 'none';
            iconEl.textContent = isCollapsed ? '▼' : '▶';
            toggleBtn.setAttribute('title', isCollapsed ? 'Collapse' : 'Expand');
        }
    }

    private updateCompareButtonState(): void {
        const compareBtn = document.getElementById('compareBtn') as HTMLButtonElement;
        const compareSection = document.getElementById('compareSection');
        if (compareBtn && compareSection) {
            const enabledPairs = this.filePairs.filter(p => p.enabled);
            compareBtn.disabled = enabledPairs.length === 0;
            if (enabledPairs.length > 0) {
                compareBtn.textContent = `Compare ${enabledPairs.length} Pair${enabledPairs.length > 1 ? 's' : ''}`;
                compareSection.style.display = 'flex';
            } else {
                compareBtn.textContent = 'Compare Files';
                compareSection.style.display = 'none';
            }
        }
    }

    private async handleCompare(): Promise<void> {
        const enabledPairs = this.filePairs.filter(p => p.enabled);
        if (enabledPairs.length === 0) {
            alert('Please select at least one file pair to compare.');
            return;
        }

        const compareBtn = document.getElementById('compareBtn') as HTMLButtonElement;
        if (compareBtn) {
            compareBtn.disabled = true;
            compareBtn.textContent = `Comparing ${enabledPairs.length} pair(s)...`;
        }

        try {
            console.log(`Starting sequential comparison of ${enabledPairs.length} file pair(s)...`);
            this.pairResults = [];
            
            let successfulComparisons = 0;
            let failedComparisons = 0;
            
            // Compare each pair sequentially with error handling
            for (let i = 0; i < enabledPairs.length; i++) {
                const pair = enabledPairs[i];
                const pairNumber = i + 1;
                
                console.log(`[${pairNumber}/${enabledPairs.length}] Comparing: ${pair.before.name} vs ${pair.after.name}`);
                
                if (compareBtn) {
                    compareBtn.textContent = `Comparing pair ${pairNumber}/${enabledPairs.length}...`;
                }
                
                try {
                    // Attempt comparison with timeout protection (increased to 5 minutes for large files)
                    const result = await Promise.race([
                        this.performPairComparison(pair),
                        new Promise<ComparisonResult>((_, reject) => 
                            setTimeout(() => reject(new Error('Comparison timeout after 5 minutes')), 300000)
                        )
                    ]);
                    
                    this.pairResults.push({ pair, result });
                    successfulComparisons++;
                    console.log(`[${pairNumber}/${enabledPairs.length}] ✓ Completed successfully`);
                    
                } catch (error) {
                    failedComparisons++;
                    const errorMessage = error instanceof Error ? error.message : String(error);
                    console.error(`[${pairNumber}/${enabledPairs.length}] ✗ Failed:`, errorMessage);
                    
                    // Create error result for this pair
                    const errorResult: ComparisonResult = {
                        metadata: {
                            reportName: pair.before.reportName || 'NEM12 Comparison',
                            reportDate: new Date().toISOString().split('T')[0],
                            reportTime: new Date().toTimeString().split(' ')[0],
                            beforeReport: pair.before.name,
                            afterReport: pair.after.name
                        },
                        details: [{
                            sr: 1,
                            issue_type: 'ERROR',
                            nmi: '',
                            record_type: '',
                            channel: '',
                            date: '',
                            field_name: '',
                            after_cell_location: '',
                            before_value: '',
                            after_value: '',
                            details: `Comparison failed: ${errorMessage}`
                        }]
                    };
                    
                    this.pairResults.push({ pair, result: errorResult });
                    
                    // Continue with next pair instead of stopping
                    console.log(`[${pairNumber}/${enabledPairs.length}] Continuing with next pair...`);
                }
            }
            
            // Display results summary
            console.log('\n=== Comparison Summary ===');
            console.log(`Total pairs: ${enabledPairs.length}`);
            console.log(`Successful: ${successfulComparisons}`);
            console.log(`Failed: ${failedComparisons}`);
            console.log('========================\n');
            
            // Show warning if some comparisons failed
            if (failedComparisons > 0) {
                const message = `${successfulComparisons} comparison(s) completed successfully.\n${failedComparisons} comparison(s) failed.\n\nResults will show error details for failed pairs.`;
                setTimeout(() => alert(message), 100);
            }
            
            // Display all results (including errors)
            this.displayMultipleResults();
            
        } catch (error) {
            // This should rarely happen as individual pair errors are caught above
            console.error('Critical comparison error:', error);
            console.error('Error stack:', error instanceof Error ? error.stack : 'No stack trace');
            alert('A critical error occurred during comparison: ' + (error instanceof Error ? error.message : String(error)) + '\n\nCheck the browser console for details.');
        } finally {
            if (compareBtn) {
                compareBtn.disabled = false;
                const enabledPairs = this.filePairs.filter(p => p.enabled);
                if (enabledPairs.length > 0) {
                    compareBtn.textContent = `Compare ${enabledPairs.length} Pair${enabledPairs.length > 1 ? 's' : ''}`;
                } else {
                    compareBtn.textContent = 'Compare Files';
                }
            }
        }
    }

    private async performPairComparison(pair: FilePair): Promise<ComparisonResult> {
        // Validate files exist and are readable
        if (!pair.before.file || !pair.after.file) {
            throw new Error('One or both files are missing');
        }

        // Check file sizes
        if (pair.before.file.size === 0) {
            throw new Error(`BEFORE file is empty: ${pair.before.name}`);
        }
        if (pair.after.file.size === 0) {
            throw new Error(`AFTER file is empty: ${pair.after.name}`);
        }

        // Read file contents with error handling
        let beforeContent: string;
        let afterContent: string;
        
        try {
            beforeContent = await this.readFileContent(pair.before.file);
        } catch (error) {
            throw new Error(`Failed to read BEFORE file (${pair.before.name}): ${error instanceof Error ? error.message : String(error)}`);
        }

        try {
            afterContent = await this.readFileContent(pair.after.file);
        } catch (error) {
            throw new Error(`Failed to read AFTER file (${pair.after.name}): ${error instanceof Error ? error.message : String(error)}`);
        }

        // Validate content is not empty
        if (!beforeContent || beforeContent.trim().length === 0) {
            throw new Error(`BEFORE file content is empty: ${pair.before.name}`);
        }
        if (!afterContent || afterContent.trim().length === 0) {
            throw new Error(`AFTER file content is empty: ${pair.after.name}`);
        }

        // Perform comparison with error handling
        let issues: ComparisonResult['details'];
        try {
            issues = this.parseAndCompareNem12(
                beforeContent, 
                afterContent, 
                pair.before.name, 
                pair.after.name
            );
        } catch (error) {
            throw new Error(`Comparison parsing failed: ${error instanceof Error ? error.message : String(error)}`);
        }

        const now = new Date();
        const reportDate = now.toISOString().split('T')[0];
        const reportTime = now.toTimeString().split(' ')[0];

        return {
            metadata: {
                reportName: pair.before.reportName || 'NEM12 Comparison',
                reportDate: reportDate,
                reportTime: reportTime,
                beforeReport: pair.before.name,
                afterReport: pair.after.name
            },
            details: issues
        };
    }


    private parseAndCompareNem12(beforeContent: string, afterContent: string, beforeFileName: string, afterFileName: string): ComparisonResult['details'] {
        const issues: ComparisonResult['details'] = [];
        
        try {
            // Parse CSV content
            const beforeRows = this.parseCSV(beforeContent);
            const afterRows = this.parseCSV(afterContent);

            console.log('Before rows:', beforeRows.length, 'After rows:', afterRows.length);

            // Parse NEM12 structure
            const beforeData = this.parseNem12Structure(beforeRows);
            const afterData = this.parseNem12Structure(afterRows);

            console.log('Before intervals:', beforeData.intervals.size, 'After intervals:', afterData.intervals.size);

        // Compare structures
        if (beforeData.firstRecordType !== '100') {
            issues.push({
                sr: issues.length + 1,
                issue_type: 'STRUCTURE',
                nmi: '',
                record_type: '',
                channel: '',
                date: '',
                field_name: '',
                after_cell_location: '',
                before_value: '',
                after_value: '',
                details: `BEFORE first record is ${beforeData.firstRecordType}`
            });
        }
        if (afterData.firstRecordType !== '100') {
            issues.push({
                sr: issues.length + 1,
                issue_type: 'STRUCTURE',
                nmi: '',
                record_type: '',
                channel: '',
                date: '',
                field_name: '',
                after_cell_location: '',
                before_value: '',
                after_value: '',
                details: `AFTER first record is ${afterData.firstRecordType}`
            });
        }

        // Compare intervals - convert to arrays with string keys for easier comparison
        console.log('Converting intervals to comparison format...');
        const beforeEntries = Array.from(beforeData.intervals.entries()).map(([key, interval]) => ({
            keyStr: JSON.stringify(key),
            key: key,
            interval: interval
        }));
        const afterEntries = Array.from(afterData.intervals.entries()).map(([key, interval]) => ({
            keyStr: JSON.stringify(key),
            key: key,
            interval: interval
        }));

        console.log('Creating key sets for comparison...');
        const beforeKeySet = new Set(beforeEntries.map(e => e.keyStr));
        const afterKeySet = new Set(afterEntries.map(e => e.keyStr));

        // Missing intervals (in before but not in after)
        console.log('Checking for missing intervals...');
        for (const entry of beforeEntries) {
            if (!afterKeySet.has(entry.keyStr)) {
                issues.push({
                    sr: issues.length + 1,
                    issue_type: 'MISSING',
                    nmi: entry.key.nmi,
                    record_type: '300',
                    channel: entry.key.channel,
                    date: entry.key.date,
                    field_name: '',
                    after_cell_location: `row ${entry.interval.rowNumber}, interval ${entry.key.intervalIndex}`,
                    before_value: entry.interval.value,
                    after_value: '',
                    details: `Interval present in BEFORE file but missing in AFTER file for NMI ${entry.key.nmi}, channel ${entry.key.channel}, date ${entry.key.date}, interval ${entry.key.intervalIndex}.`
                });
            }
        }

        // Extra intervals (in after but not in before)
        console.log('Checking for extra intervals...');
        for (const entry of afterEntries) {
            if (!beforeKeySet.has(entry.keyStr)) {
                issues.push({
                    sr: issues.length + 1,
                    issue_type: 'EXTRA',
                    nmi: entry.key.nmi,
                    record_type: '300',
                    channel: entry.key.channel,
                    date: entry.key.date,
                    field_name: '',
                    after_cell_location: `row ${entry.interval.rowNumber}, interval ${entry.key.intervalIndex}`,
                    before_value: '',
                    after_value: entry.interval.value,
                    details: `Extra interval present only in AFTER file (not in BEFORE file) for NMI ${entry.key.nmi}, channel ${entry.key.channel}, date ${entry.key.date}, interval ${entry.key.intervalIndex}.`
                });
            }
        }

        // Value mismatches (in both but different values)
        console.log('Checking for value mismatches...');
        // Create a Map for O(1) lookup instead of O(n) find() in loop - CRITICAL for performance
        const afterEntryMap = new Map<string, typeof afterEntries[0]>();
        afterEntries.forEach(entry => {
            afterEntryMap.set(entry.keyStr, entry);
        });

        for (const beforeEntry of beforeEntries) {
            if (afterKeySet.has(beforeEntry.keyStr)) {
                const afterEntry = afterEntryMap.get(beforeEntry.keyStr);
                if (afterEntry && beforeEntry.interval.value !== afterEntry.interval.value) {
                    issues.push({
                        sr: issues.length + 1,
                        issue_type: 'VALUE_MISMATCH',
                        nmi: beforeEntry.key.nmi,
                        record_type: '300',
                        channel: beforeEntry.key.channel,
                        date: beforeEntry.key.date,
                        field_name: 'IntervalValue',
                        after_cell_location: `row ${afterEntry.interval.rowNumber}, interval ${beforeEntry.key.intervalIndex}`,
                        before_value: beforeEntry.interval.value,
                        after_value: afterEntry.interval.value,
                        details: `Value mismatch between BEFORE and AFTER files (${beforeFileName}=${beforeEntry.interval.value} vs ${afterFileName}=${afterEntry.interval.value}).`
                    });
                }
            }
        }

        console.log('Comparison complete. Total issues found:', issues.length);

        } catch (error) {
            // Re-throw with context for better error handling upstream
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error('Error in parseAndCompareNem12:', error);
            throw new Error(`NEM12 parsing/comparison error: ${errorMessage}`);
        }

        return issues;
    }

    private parseCSV(content: string): string[][] {
        const lines = content.split(/\r?\n/);
        const rows: string[][] = [];
        
        // Detect delimiter from first non-empty line
        let delimiter = ',';
        for (const line of lines) {
            if (line.trim()) {
                const delimiters = [',', '|', ';', '\t'];
                let bestDelimiter = delimiters[0];
                let bestCount = (line.match(new RegExp('\\' + delimiters[0], 'g')) || []).length;
                
                for (const delim of delimiters.slice(1)) {
                    const count = (line.match(new RegExp('\\' + delim, 'g')) || []).length;
                    if (count > bestCount) {
                        bestCount = count;
                        bestDelimiter = delim;
                    }
                }
                delimiter = bestDelimiter;
                break;
            }
        }
        
        // Parse rows with detected delimiter
        for (const line of lines) {
            if (!line.trim()) continue;
            
            // Simple CSV parsing - split by delimiter and trim
            const row = line.split(delimiter).map(cell => {
                // Remove quotes if present
                let trimmed = cell.trim();
                if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
                    (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
                    trimmed = trimmed.slice(1, -1);
                }
                return trimmed;
            });
            rows.push(row);
        }
        
        return rows;
    }

    private parseNem12Structure(rows: string[][]): {
        firstRecordType: string;
        intervals: Map<{nmi: string, channel: string, date: string, intervalIndex: number}, {value: string, rowNumber: number}>;
    } {
        const intervals = new Map();
        let firstRecordType = '';
        let currentNmi = '';
        let currentChannel = '';
        let intervalLength = 30;

        for (let rowNum = 0; rowNum < rows.length; rowNum++) {
            const row = rows[rowNum];
            if (row.length === 0) continue;

            const recordType = row[0].trim();
            if (!firstRecordType) {
                firstRecordType = recordType;
            }

            if (recordType === '200') {
                currentNmi = (row[1] || '').trim();
                // Channel can be at index 4 or 2
                currentChannel = (row[4] || row[2] || 'UNKNOWN_CHANNEL').trim();
                const intervalLen = parseInt((row[8] || row[7] || '30').trim(), 10);
                intervalLength = isNaN(intervalLen) || intervalLen <= 0 ? 30 : intervalLen;
            } else if (recordType === '300' && currentNmi && currentChannel) {
                const date = (row[1] || '').trim();
                if (!date) continue;
                
                // Find quality flag index (last single character from end that's A,V,E,F,N,S,R,C,D)
                let qualityIdx = -1;
                const qualityFlags = ['A', 'V', 'E', 'F', 'N', 'S', 'R', 'C', 'D'];
                for (let i = row.length - 1; i >= 2; i--) {
                    const val = (row[i] || '').trim();
                    if (val && val.length === 1 && qualityFlags.includes(val)) {
                        qualityIdx = i;
                        break;
                    }
                }

                let values: string[] = [];
                if (qualityIdx > 2) {
                    values = row.slice(2, qualityIdx).map(v => (v || '').trim());
                } else {
                    // Calculate expected number of intervals
                    const expected = intervalLength === 30 ? 48 : Math.max(1, Math.floor((24 * 60) / Math.max(1, intervalLength)));
                    const endIdx = Math.min(2 + expected, row.length);
                    values = row.slice(2, endIdx).map(v => (v || '').trim());
                }

                for (let idx = 0; idx < values.length; idx++) {
                    const key = { nmi: currentNmi, channel: currentChannel, date: date, intervalIndex: idx };
                    if (!intervals.has(key) || !intervals.get(key).value) {
                        intervals.set(key, { value: values[idx] || '', rowNumber: rowNum + 1 });
                    }
                }
            }
        }

        return { firstRecordType, intervals };
    }

    private readFileContent(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target?.result as string);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    private displayMultipleResults(): void {
        const resultsSection = document.getElementById('resultsSection');
        const pairResultsContainer = document.getElementById('pairResultsContainer');
        if (!resultsSection || !pairResultsContainer) return;

        resultsSection.style.display = 'block';

        // Calculate overall summary
        let overallCritical = 0;
        let overallMismatch = 0;
        let overallTotal = 0;

        this.pairResults.forEach(pairResult => {
            const details = pairResult.result.details;
            const critical = details.filter(d => ['STRUCTURE', 'MISSING', 'EXTRA'].includes(d.issue_type)).length;
            const mismatch = details.filter(d => d.issue_type === 'VALUE_MISMATCH').length;
            overallCritical += critical;
            overallMismatch += mismatch;
            overallTotal += details.length;
        });

        // Update overall summary
        const overallHighEl = document.getElementById('overallHighCount');
        const overallMediumEl = document.getElementById('overallMediumCount');
        const overallTotalEl = document.getElementById('overallTotalCount');

        if (overallHighEl) overallHighEl.textContent = overallCritical.toString();
        if (overallMediumEl) overallMediumEl.textContent = overallMismatch.toString();
        if (overallTotalEl) overallTotalEl.textContent = overallTotal.toString();

        // Render pair-wise results
        pairResultsContainer.innerHTML = this.pairResults.map((pairResult, idx) => {
            const details = pairResult.result.details;
            const critical = details.filter(d => ['STRUCTURE', 'MISSING', 'EXTRA'].includes(d.issue_type)).length;
            const mismatch = details.filter(d => d.issue_type === 'VALUE_MISMATCH').length;
            const total = details.length;
            const pairId = `pair_result_${pairResult.pair.id}`;

            return `
                <div class="pair-result-card" id="${pairId}">
                    <div class="pair-result-header">
                        <div class="pair-result-title">
                            <button class="collapse-toggle-btn" data-pair-id="${pairId}" onclick="window.nem12UI.togglePairCollapse('${pairId}')" title="Collapse/Expand">
                                <span class="collapse-icon">▼</span>
                            </button>
                            <span class="pair-number-badge">Pair ${idx + 1}</span>
                        </div>
                        <div class="pair-result-summary">
                            <div class="summary-badge-compact">
                                <span class="summary-value-compact">${total}</span>
                                <span class="summary-label-compact">Total</span>
                            </div>
                            <div class="summary-badge-compact">
                                <span class="summary-value-compact">${critical}</span>
                                <span class="summary-label-compact">Critical</span>
                            </div>
                            <div class="summary-badge-compact">
                                <span class="summary-value-compact">${mismatch}</span>
                                <span class="summary-label-compact">Mismatch</span>
                            </div>
                        </div>
                    </div>
                    <div class="pair-result-content" id="content_${pairId}">
                        <div class="pair-result-files">
                            <div class="pair-file-info">
                                <span class="file-label before-label">BEFORE:</span>
                                <span class="file-name">${this.escapeHtml(pairResult.pair.before.name)}</span>
                            </div>
                            <div class="pair-file-info">
                                <span class="file-label after-label">AFTER:</span>
                                <span class="file-name">${this.escapeHtml(pairResult.pair.after.name)}</span>
                            </div>
                        </div>
                        <div class="pair-result-table-container" id="table_${pairId}"></div>
                    </div>
                </div>
            `;
        }).join('');

        // Render table for each pair
        this.pairResults.forEach((pairResult) => {
            const pairId = `pair_result_${pairResult.pair.id}`;
            const tableEl = document.getElementById(`table_${pairId}`);
            if (tableEl) {
                this.currentDetails = pairResult.result.details;
                this.renderTable(pairResult.result.details, pairResult.result.metadata, tableEl);
            }
        });

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    private switchTab(tabId: string): void {
        // Update tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`[data-tab-id="${tabId}"]`);
        if (activeBtn) activeBtn.classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        const activeContent = document.getElementById(tabId);
        if (activeContent) activeContent.classList.add('active');

        this.activeTab = tabId;
    }

    private displayResults(results: ComparisonResult): void {
        const resultsSection = document.getElementById('resultsSection');
        if (!resultsSection) return;

        resultsSection.style.display = 'block';

        // Store original details for filtering/sorting
        this.currentDetails = results.details || [];
        
        // Show search container
        const searchContainer = document.getElementById('searchContainer');
        if (searchContainer && this.currentDetails.length > 0) {
            searchContainer.style.display = 'block';
        }

        // Count issues by type for summary
        const structureCount = results.details.filter(d => d.issue_type === 'STRUCTURE').length;
        const missingCount = results.details.filter(d => d.issue_type === 'MISSING').length;
        const extraCount = results.details.filter(d => d.issue_type === 'EXTRA').length;
        const mismatchCount = results.details.filter(d => d.issue_type === 'VALUE_MISMATCH').length;

        // Update summary counts (using issue types as severity indicators)
        const highCountEl = document.getElementById('highCount');
        const mediumCountEl = document.getElementById('mediumCount');
        const totalCountEl = document.getElementById('totalCount');

        const criticalCount = structureCount + missingCount + extraCount;
        const totalIssues = results.details.length;

        if (highCountEl) highCountEl.textContent = criticalCount.toString();
        if (mediumCountEl) mediumCountEl.textContent = mismatchCount.toString();
        if (totalCountEl) totalCountEl.textContent = totalIssues.toString();

        // Display details table
        const resultsTable = document.getElementById('resultsTable');
        if (resultsTable && results.details && results.details.length > 0) {
            this.renderTable(this.currentDetails, results.metadata);
        } else if (resultsTable) {
            resultsTable.innerHTML = '<p style="color: #666; padding: 20px; text-align: center;">No differences found.</p>';
            if (searchContainer) searchContainer.style.display = 'none';
        }

        // Initialize search and sort
        this.initializeSearchAndSort();

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    private initializeSearchAndSort(): void {
        const searchInput = document.getElementById('searchInput') as HTMLInputElement;
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const target = e.target as HTMLInputElement;
                this.filterTable(target.value);
            });
        }

        const resetBtn = document.getElementById('resetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetView();
            });
        }
    }

    private resetPage(): void {
        if (confirm('Are you sure you want to reset? This will reload the page and clear all data.')) {
            window.location.reload();
        }
    }

    private resetView(): void {
        // Clear search
        const searchInputInline = document.getElementById('searchInputInline') as HTMLInputElement;
        if (searchInputInline) {
            searchInputInline.value = '';
        }

        // Reset sorting
        this.sortColumn = null;
        this.sortDirection = 'asc';

        // Reset to original data
        if (this.results && this.results.details) {
            this.currentDetails = [...this.results.details];
            this.renderTable(this.currentDetails, this.results.metadata);
        }
    }

    private filterTable(searchTerm: string): void {
        if (!this.currentDetails || this.currentDetails.length === 0) return;

        const term = searchTerm.toLowerCase().trim();
        let filtered = this.currentDetails;

        if (term) {
            filtered = this.currentDetails.filter(detail => {
                return (
                    (detail.sr?.toString() || '').toLowerCase().includes(term) ||
                    (detail.issue_type || '').toLowerCase().includes(term) ||
                    (detail.nmi || '').toLowerCase().includes(term) ||
                    (detail.record_type || '').toLowerCase().includes(term) ||
                    (detail.channel || '').toLowerCase().includes(term) ||
                    (detail.date || '').toLowerCase().includes(term) ||
                    (detail.field_name || '').toLowerCase().includes(term) ||
                    (detail.after_cell_location || '').toLowerCase().includes(term) ||
                    (detail.before_value || '').toLowerCase().includes(term) ||
                    (detail.after_value || '').toLowerCase().includes(term) ||
                    (detail.details || '').toLowerCase().includes(term)
                );
            });
        }

        this.currentDetails = filtered;
        // Find the active tab's table container
        const activeTabContent = document.querySelector('.tab-content.active');
        const tableEl = activeTabContent ? activeTabContent.querySelector('.pair-results-table') as HTMLElement : null;
        if (tableEl && this.activeTab) {
            const pairResult = this.pairResults.find(pr => `tab_${pr.pair.id}` === this.activeTab);
            if (pairResult) {
                this.renderTable(filtered, pairResult.result.metadata, tableEl);
            }
        } else if (this.results) {
            this.renderTable(filtered, this.results.metadata);
        }
    }

    private sortTable(columnIndex: number): void {
        if (!this.currentDetails || this.currentDetails.length === 0) return;

        // Toggle sort direction if clicking the same column
        if (this.sortColumn === columnIndex) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = columnIndex;
            this.sortDirection = 'asc';
        }

        const sorted = [...this.currentDetails].sort((a, b) => {
            let aVal: string | number;
            let bVal: string | number;

            switch (columnIndex) {
                case 0: aVal = a.sr; bVal = b.sr; break; // Sr
                case 1: aVal = a.issue_type || ''; bVal = b.issue_type || ''; break; // issue_type
                case 2: aVal = a.nmi || ''; bVal = b.nmi || ''; break; // nmi
                case 3: aVal = a.record_type || ''; bVal = b.record_type || ''; break; // record_type
                case 4: aVal = a.channel || ''; bVal = b.channel || ''; break; // channel
                case 5: aVal = a.date || ''; bVal = b.date || ''; break; // date
                case 6: aVal = a.field_name || ''; bVal = b.field_name || ''; break; // field_name
                case 7: aVal = a.after_cell_location || ''; bVal = b.after_cell_location || ''; break; // after_cell_location
                case 8: aVal = a.before_value || ''; bVal = b.before_value || ''; break; // before_value
                case 9: aVal = a.after_value || ''; bVal = b.after_value || ''; break; // after_value
                case 10: aVal = a.details || ''; bVal = b.details || ''; break; // details
                default: return 0;
            }

            // Handle numeric comparison for Sr
            if (columnIndex === 0) {
                aVal = Number(aVal) || 0;
                bVal = Number(bVal) || 0;
            } else {
                aVal = String(aVal).toLowerCase();
                bVal = String(bVal).toLowerCase();
            }

            if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
            return 0;
        });

        this.currentDetails = sorted;
        this.renderTable(sorted, this.results.metadata);
    }

    private renderTable(details: ComparisonResult['details'], metadata: ComparisonResult['metadata'], container?: HTMLElement): void {
        const resultsTable = container || document.getElementById('resultsTable');
        if (!resultsTable) return;

        // Show metadata and success message
        let html = '';
        if (details.length === 0) {
            html += '<div class="success-message" style="margin-bottom: 20px; padding: 20px; background: #dcfce7; border: 1px solid #16a34a; border-radius: 6px; text-align: center;">';
            html += '<p style="font-size: 16px; font-weight: 600; color: #16a34a; margin: 0;">✓ No differences found - Files are identical!</p>';
            html += `<p style="font-size: 12px; color: #666; margin: 8px 0 0 0;">Report Date: ${metadata.reportDate} Time: ${metadata.reportTime}</p>`;
            html += '</div>';
        } else {
            html += '<div class="metadata-info" style="margin-bottom: 20px; padding: 12px; background: #f9f9f9; border-radius: 4px;">';
            html += `<p><strong>Report Date:</strong> ${metadata.reportDate} <strong>Time:</strong> ${metadata.reportTime}</p>`;
            html += `<p><strong>Showing:</strong> ${details.length} of ${this.results?.details.length || details.length} issues</p>`;
            html += '</div>';
        }

        // Search container below metadata (only show if there are issues)
        if (details.length > 0) {
            html += '<div class="search-container" id="searchContainerInline" style="display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-bottom: 12px;">';
            html += '<input type="text" id="searchInputInline" class="search-input" placeholder="Search anything from results">';
            html += '<button class="export-btn" id="exportBtn" title="Download result">Download Result</button>';
            html += '</div>';
        }

        // Always show table (even if empty)
        html += '<table class="results-table"><thead><tr>';
        const headers = ['Sr', 'issue_type', 'nmi', 'record_type', 'channel', 'date', 'field_name', 'after_cell_location', 'before_value', 'after_value', 'details'];
        
        // No sorting - all columns are non-sortable
        headers.forEach((header) => {
            html += `<th>${header}</th>`;
        });
        // Add reset button as last column header (but not as a real column)
        html += '<th class="reset-header" style="width: 50px; text-align: center; position: relative;"><button class="reset-icon-btn" id="resetBtnInline" title="Reset search and sorting" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%);">↺</button></th>';
        html += '</tr></thead><tbody>';

        if (details.length === 0) {
            html += '<tr><td colspan="12" style="text-align: center; padding: 20px; color: #666;">No differences found - All data matches</td></tr>';
        } else {
            details.forEach(detail => {
                html += '<tr>';
                html += `<td class="td-numeric">${detail.sr}</td>`;
                html += `<td class="td-issue-type">${this.escapeHtml(detail.issue_type)}</td>`;
                html += `<td class="td-nmi">${this.escapeHtml(detail.nmi || '-')}</td>`;
                html += `<td class="td-record-type">${this.escapeHtml(detail.record_type || '-')}</td>`;
                html += `<td class="td-channel">${this.escapeHtml(detail.channel || '-')}</td>`;
                html += `<td class="td-date">${this.escapeHtml(detail.date || '-')}</td>`;
                html += `<td class="td-field-name">${this.escapeHtml(detail.field_name || '-')}</td>`;
                html += `<td class="td-cell-location">${this.escapeHtml(detail.after_cell_location || '-')}</td>`;
                html += `<td class="td-value">${this.escapeHtml(detail.before_value || '-')}</td>`;
                html += `<td class="td-value">${this.escapeHtml(detail.after_value || '-')}</td>`;
                html += `<td class="td-details">${this.escapeHtml(detail.details || '-')}</td>`;
                html += '</tr>';
            });
        }

        html += '</tbody></table>';

        resultsTable.innerHTML = html;

        // Initialize inline search
        const searchInputInline = document.getElementById('searchInputInline') as HTMLInputElement;
        if (searchInputInline) {
            searchInputInline.removeEventListener('input', this.searchHandler as EventListener);
            this.searchHandler = (e: Event) => {
                const target = e.target as HTMLInputElement;
                this.filterTable(target.value);
            };
            searchInputInline.addEventListener('input', this.searchHandler);
        }

        // Initialize inline reset button
        const resetBtnInline = document.getElementById('resetBtnInline');
        if (resetBtnInline) {
            resetBtnInline.removeEventListener('click', this.resetHandler as EventListener);
            this.resetHandler = () => {
                this.resetView();
            };
            resetBtnInline.addEventListener('click', this.resetHandler);
        }

        // Initialize export button
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.removeEventListener('click', this.exportHandler as EventListener);
            this.exportHandler = () => {
                this.exportToCSV();
            };
            exportBtn.addEventListener('click', this.exportHandler);
        }

        // Sorting removed - no click handlers needed
    }

    private exportToCSV(): void {
        // Check if we're in multiple results mode or single result mode
        let dataToExport: ComparisonResult['details'];
        let metadata: ComparisonResult['metadata'];

        if (this.pairResults && this.pairResults.length > 0) {
            // Multiple results mode - find which pair's export button was clicked
            const exportBtn = document.getElementById('exportBtn');
            let selectedPairResult: PairComparisonResult | null = null;
            
            if (exportBtn) {
                // Find the parent pair result card
                let parentCard = exportBtn.closest('.pair-result-card');
                if (parentCard) {
                    const pairId = parentCard.id;
                    selectedPairResult = this.pairResults.find(pr => `pair_result_${pr.pair.id}` === pairId) || null;
                }
            }
            
            // If not found, use the first non-collapsed pair, or just the first one
            if (!selectedPairResult) {
                for (const pairResult of this.pairResults) {
                    const pairId = `pair_result_${pairResult.pair.id}`;
                    const contentEl = document.getElementById(`content_${pairId}`);
                    if (!contentEl || contentEl.style.display !== 'none') {
                        selectedPairResult = pairResult;
                        break;
                    }
                }
            }
            
            // Fallback to first result
            if (!selectedPairResult && this.pairResults.length > 0) {
                selectedPairResult = this.pairResults[0];
            }
            
            if (selectedPairResult) {
                dataToExport = this.currentDetails.length > 0 ? this.currentDetails : selectedPairResult.result.details;
                metadata = selectedPairResult.result.metadata;
            } else {
                alert('No data to export');
                return;
            }
        } else if (this.results && this.results.details && this.results.details.length > 0) {
            // Single result mode
            dataToExport = this.currentDetails.length > 0 ? this.currentDetails : this.results.details;
            metadata = this.results.metadata;
        } else {
            alert('No data to export');
            return;
        }

        if (!dataToExport || dataToExport.length === 0) {
            alert('No data to export');
            return;
        }

        // Build CSV content matching Python output format
        let csvContent = '';

        // Metadata header
        csvContent += `Report_Name,${metadata.reportName}\n`;
        csvContent += `Report_Date,${metadata.reportDate}\n`;
        csvContent += `Report_Time,${metadata.reportTime}\n`;
        csvContent += `Before_Report,${metadata.beforeReport}\n`;
        csvContent += `After_Report,${metadata.afterReport}\n`;
        csvContent += '\n'; // Blank separator row

        // Detail header (with filename in after_cell_location header)
        csvContent += `Sr,issue_type,nmi,record_type,channel,date,field_name,after_cell_location (${metadata.afterReport}),before_value,after_value,details\n`;

        // Detail rows
        dataToExport.forEach(detail => {
            const row = [
                detail.sr,
                detail.issue_type,
                detail.nmi || '',
                detail.record_type || '',
                detail.channel || '',
                detail.date || '',
                detail.field_name || '',
                detail.after_cell_location || '',
                detail.before_value || '',
                detail.after_value || '',
                this.escapeCSVField(detail.details || '')
            ];
            csvContent += row.join(',') + '\n';
        });

        // Create blob and download with proper naming
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        // Generate filename: comparison_results_YYYYMMDD_HHMMSS_BeforeFile_AfterFile.csv
        const date = new Date();
        const dateStr = date.toISOString().split('T')[0].replace(/-/g, '');
        const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
        
        // Clean filenames for use in download name
        const beforeName = metadata.beforeReport.replace(/\.(csv|txt|nem12)$/i, '').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);
        const afterName = metadata.afterReport.replace(/\.(csv|txt|nem12)$/i, '').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);
        
        const filename = `comparison_results_${dateStr}_${timeStr}_${beforeName}_vs_${afterName}.csv`;
        
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    private downloadAllResults(): void {
        if (!this.pairResults || this.pairResults.length === 0) {
            alert('No comparison results to download');
            return;
        }

        // Download each pair's result
        this.pairResults.forEach((pairResult, index) => {
            setTimeout(() => {
                const metadata = pairResult.result.metadata;
                const details = pairResult.result.details;

                // Build CSV content matching Python output format
                let csvContent = '';

                // Metadata header
                csvContent += `Report_Name,${metadata.reportName}\n`;
                csvContent += `Report_Date,${metadata.reportDate}\n`;
                csvContent += `Report_Time,${metadata.reportTime}\n`;
                csvContent += `Before_Report,${metadata.beforeReport}\n`;
                csvContent += `After_Report,${metadata.afterReport}\n`;
                csvContent += '\n'; // Blank separator row

                // Detail header
                csvContent += `Sr,issue_type,nmi,record_type,channel,date,field_name,after_cell_location (${metadata.afterReport}),before_value,after_value,details\n`;

                // Detail rows
                details.forEach(detail => {
                    const row = [
                        detail.sr,
                        detail.issue_type,
                        detail.nmi || '',
                        detail.record_type || '',
                        detail.channel || '',
                        detail.date || '',
                        detail.field_name || '',
                        detail.after_cell_location || '',
                        detail.before_value || '',
                        detail.after_value || '',
                        this.escapeCSVField(detail.details || '')
                    ];
                    csvContent += row.join(',') + '\n';
                });

                // Create blob and download
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                const url = URL.createObjectURL(blob);
                
                // Generate filename: comparison_results_YYYYMMDD_HHMMSS_PairX_BeforeFile_AfterFile.csv
                const date = new Date();
                const dateStr = date.toISOString().split('T')[0].replace(/-/g, '');
                const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
                
                // Clean filenames for use in download name
                const beforeName = metadata.beforeReport.replace(/\.(csv|txt|nem12)$/i, '').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);
                const afterName = metadata.afterReport.replace(/\.(csv|txt|nem12)$/i, '').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);
                
                const filename = `comparison_results_${dateStr}_${timeStr}_Pair${index + 1}_${beforeName}_vs_${afterName}.csv`;
                
                link.setAttribute('href', url);
                link.setAttribute('download', filename);
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }, index * 200); // Stagger downloads by 200ms
        });

        alert(`Downloading ${this.pairResults.length} comparison result file(s)...`);
    }

    private escapeCSVField(field: string): string {
        // Escape quotes and wrap in quotes if contains comma, newline, or quote
        if (field.includes(',') || field.includes('\n') || field.includes('"')) {
            return '"' + field.replace(/"/g, '""') + '"';
        }
        return field;
    }

    private generateResultsTable(details: ComparisonResult['details'], metadata: ComparisonResult['metadata']): string {
        // This method is deprecated, use renderTable instead
        return '';
        let html = '<div class="metadata-info" style="margin-bottom: 20px; padding: 12px; background: #f9f9f9; border-radius: 4px;">';
        html += `<p><strong>Report Name:</strong> ${metadata.reportName}</p>`;
        html += `<p><strong>Report Date:</strong> ${metadata.reportDate} <strong>Time:</strong> ${metadata.reportTime}</p>`;
        html += `<p><strong>Before Report:</strong> ${metadata.beforeReport} <strong>After Report:</strong> ${metadata.afterReport}</p>`;
        html += '</div>';

        html += '<table class="results-table"><thead><tr>';
        html += '<th>Sr</th>';
        html += '<th>issue_type</th>';
        html += '<th>nmi</th>';
        html += '<th>record_type</th>';
        html += '<th>channel</th>';
        html += '<th>date</th>';
        html += '<th>field_name</th>';
        html += '<th>after_cell_location</th>';
        html += '<th>before_value</th>';
        html += '<th>after_value</th>';
        html += '<th>details</th>';
        html += '</tr></thead><tbody>';

        details.forEach(detail => {
            html += '<tr>';
            html += `<td>${detail.sr}</td>`;
            html += `<td>${detail.issue_type}</td>`;
            html += `<td>${detail.nmi || '-'}</td>`;
            html += `<td>${detail.record_type || '-'}</td>`;
            html += `<td>${detail.channel || '-'}</td>`;
            html += `<td>${detail.date || '-'}</td>`;
            html += `<td>${detail.field_name || '-'}</td>`;
            html += `<td>${detail.after_cell_location || '-'}</td>`;
            html += `<td>${detail.before_value || '-'}</td>`;
            html += `<td>${detail.after_value || '-'}</td>`;
            html += `<td>${detail.details || '-'}</td>`;
            html += '</tr>';
        });

        html += '</tbody></table>';
        return html;
    }
}

// Initialize the UI when DOM is ready
let nem12UIInstance: Nem12ComparisonUI;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        nem12UIInstance = new Nem12ComparisonUI();
    });
} else {
    nem12UIInstance = new Nem12ComparisonUI();
}
