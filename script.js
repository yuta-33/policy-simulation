// アプリケーションのメインクラス
class PolicyBudgetSimulator {
    constructor() {
        this.currentProject = null;
        this.similarProjects = [];
        this.currentTab = 'all';
        this.historyPage = 1;
        this.historyLimit = 10;
        this.init();
    }

    // 初期化
    init() {
        this.bindEvents();
        this.loadSampleData();
        this.updateKPI();
    }

    // イベントバインディング
    bindEvents() {
        // フォーム送信
        document.getElementById('projectForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit();
        });

        // ヘッダーボタン
        document.getElementById('newProjectBtn').addEventListener('click', () => {
            this.newProject();
        });

        document.getElementById('saveBtn').addEventListener('click', () => {
            this.saveProject();
        });

        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportData();
        });

        // タブ切り替え
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // 履歴関連のイベント
        document.getElementById('refreshHistoryBtn').addEventListener('click', () => {
            this.loadHistory();
        });

        document.getElementById('exportHistoryBtn').addEventListener('click', () => {
            this.exportHistory();
        });

        document.getElementById('applyFiltersBtn').addEventListener('click', () => {
            this.historyPage = 1;
            this.loadHistory();
        });

        document.getElementById('prevPageBtn').addEventListener('click', () => {
            if (this.historyPage > 1) {
                this.historyPage--;
                this.loadHistory();
            }
        });

        document.getElementById('nextPageBtn').addEventListener('click', () => {
            this.historyPage++;
            this.loadHistory();
        });

        // モーダル閉じる
        document.getElementById('modalClose').addEventListener('click', () => {
            this.closeModal();
        });

        // モーダル外クリックで閉じる
        document.getElementById('projectModal').addEventListener('click', (e) => {
            if (e.target.id === 'projectModal') {
                this.closeModal();
            }
        });

        // 予算入力時のリアルタイム更新
        document.getElementById('initialBudget').addEventListener('input', (e) => {
            this.updateProposedBudget(e.target.value);
        });
    }

    // フォーム送信処理
    handleFormSubmit() {
        const formData = new FormData(document.getElementById('projectForm'));
        const projectData = {
            currentSituation: formData.get('currentSituation'),
            projectName: formData.get('projectName'),
            projectOverview: formData.get('projectOverview'),
            initialBudget: parseInt(formData.get('initialBudget')) || 0
        };

        this.currentProject = projectData;
        this.analyzeSimilarProjects();
        this.updateKPI();
        this.showToast('分析が完了しました', 'success');
    }

    // 類似事業の分析
    async analyzeSimilarProjects() {
        if (!this.currentProject) return;

        try {
            // バックエンドAPIに分析リクエストを送信
            const response = await fetch('http://localhost:5000/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    issue_text: this.currentProject.currentSituation,
                    summary_text: this.currentProject.projectOverview
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const analysisResult = await response.json();
            
            // 分析結果を処理
            if (analysisResult.error) {
                console.error('分析エラー:', analysisResult.message);
                this.showToast('分析中にエラーが発生しました', 'error');
                return;
            }

            // 類似事業を設定
            this.similarProjects = analysisResult.similar_cases.map(case_data => ({
                id: case_data.id,
                name: case_data.name,
                year: case_data.year,
                budget: parseInt(case_data.budget),
                rating: case_data.eval,
                description: case_data.details,
                outcomes: case_data.details,
                similarity: case_data.similarity,
                weight: case_data.weight
            }));

            // KPIを更新
            this.updateKPIFromBackend(analysisResult);
            
            // プロジェクトリストを更新
            this.renderProjectsList();
            
            this.showToast('分析が完了しました', 'success');
            
        } catch (error) {
            console.error('分析リクエストエラー:', error);
            
            // エラー時はサンプルデータを使用
            this.similarProjects = this.sampleProjects.filter(project => {
                const budgetDiff = Math.abs(project.budget - this.currentProject.initialBudget);
                const budgetThreshold = this.currentProject.initialBudget * 0.3; // 30%以内
                return budgetDiff <= budgetThreshold;
            });
            
            this.renderProjectsList();
            this.showToast('バックエンドに接続できませんでした。サンプルデータを使用します。', 'info');
        }
    }

    // プロジェクトリストの表示
    renderProjectsList() {
        const projectsList = document.getElementById('projectsList');
        
        if (this.similarProjects.length === 0) {
            projectsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <p>類似の過去事業が見つかりませんでした</p>
                </div>
            `;
            return;
        }

        const filteredProjects = this.filterProjectsByTab(this.similarProjects);
        
        projectsList.innerHTML = filteredProjects.map(project => `
            <div class="project-item" onclick="app.showProjectModal('${project.id}')">
                <div class="project-header">
                    <span class="project-name">${project.name}</span>
                    <span class="project-budget">¥${project.budget.toLocaleString()}</span>
                </div>
                <div class="project-rating">
                    <span class="rating-badge rating-${project.rating.toLowerCase()}">評価: ${project.rating}</span>
                    <span>${project.year}年度</span>
                </div>
            </div>
        `).join('');
    }

    // タブによるフィルタリング
    filterProjectsByTab(projects) {
        switch (this.currentTab) {
            case 'high-rated':
                return projects.filter(p => ['A', 'B'].includes(p.rating));
            case 'needs-improvement':
                return projects.filter(p => ['C', 'D'].includes(p.rating));
            default:
                return projects;
        }
    }

    // タブ切り替え
    switchTab(tabName) {
        this.currentTab = tabName;
        
        // タブボタンのアクティブ状態を更新
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // 履歴タブの場合は履歴を表示
        if (tabName === 'history') {
            this.showHistoryTab();
        } else {
            this.hideHistoryTab();
            // プロジェクトリストを再表示
            this.renderProjectsList();
        }
    }

    // プロジェクト詳細モーダル表示
    showProjectModal(projectId) {
        const project = this.sampleProjects.find(p => p.id === projectId);
        if (!project) return;

        document.getElementById('modalProjectName').textContent = project.name;
        document.getElementById('modalBody').innerHTML = `
            <div class="project-details">
                <div class="detail-row">
                    <strong>事業年度:</strong> ${project.year}年度
                </div>
                ${project.ministry ? `
                    <div class="detail-row">
                        <strong>府省庁:</strong> ${project.ministry}
                    </div>
                ` : ''}
                ${project.bureau ? `
                    <div class="detail-row">
                        <strong>局・庁:</strong> ${project.bureau}
                    </div>
                ` : ''}
                <div class="detail-row">
                    <strong>投下予算:</strong> ¥${parseInt(project.budget).toLocaleString()}
                </div>
                ${project.scale_category ? `
                    <div class="detail-row">
                        <strong>規模区分:</strong> ${project.scale_category}
                    </div>
                ` : ''}
                <div class="detail-row">
                    <strong>評価:</strong> 
                    <span class="rating-badge rating-${project.eval.toLowerCase()}">${project.eval}</span>
                </div>
                <div class="detail-row">
                    <strong>事業概要:</strong>
                    <p>${project.description || project.details}</p>
                </div>
                <div class="detail-row">
                    <strong>成果・課題:</strong>
                    <p>${project.outcomes || project.details}</p>
                </div>
                ${project.similarity !== undefined ? `
                    <div class="detail-row">
                        <strong>類似度:</strong> ${(project.similarity * 100).toFixed(1)}%
                    </div>
                ` : ''}
            </div>
        `;

        document.getElementById('projectModal').style.display = 'block';
    }

    // モーダルを閉じる
    closeModal() {
        document.getElementById('projectModal').style.display = 'none';
    }

    // KPI更新
    updateKPI() {
        if (!this.currentProject) {
            this.resetKPI();
            return;
        }

        const proposedBudget = this.currentProject.initialBudget;
        const averageBudget = this.calculateAverageBudget();
        const budgetComparison = proposedBudget - averageBudget;
        const similarCount = this.similarProjects.length;

        // 提案事業予算
        document.getElementById('proposedBudgetValue').textContent = `¥${proposedBudget.toLocaleString()}`;

        // 類似事業平均予算
        document.getElementById('averageBudgetValue').textContent = `¥${averageBudget.toLocaleString()}`;

        // 予算比較
        const comparisonElement = document.getElementById('budgetComparisonValue');
        comparisonElement.textContent = `¥${budgetComparison.toLocaleString()}`;
        
        // 警告色の適用
        const comparisonCard = document.getElementById('budgetComparisonCard');
        if (budgetComparison < 0) {
            comparisonCard.classList.add('warning');
        } else {
            comparisonCard.classList.remove('warning');
        }

        // 類似事業件数
        document.getElementById('similarProjectsValue').textContent = `${similarCount}件`;
    }

    // バックエンドからの分析結果でKPIを更新
    updateKPIFromBackend(analysisResult) {
        if (!analysisResult) return;

        // 予測予算を表示（提案予算の参考値として）
        const predictedBudget = analysisResult.predicted_budget;
        if (predictedBudget > 0) {
            document.getElementById('averageBudgetValue').textContent = `¥${predictedBudget.toLocaleString()}`;
        }

        // 類似事業件数
        const caseCount = analysisResult.case_count;
        document.getElementById('similarProjectsValue').textContent = `${caseCount}件`;

        // 予算比較を再計算
        if (this.currentProject) {
            const proposedBudget = this.currentProject.initialBudget;
            const budgetComparison = proposedBudget - predictedBudget;
            
            const comparisonElement = document.getElementById('budgetComparisonValue');
            comparisonElement.textContent = `¥${budgetComparison.toLocaleString()}`;
            
            // 警告色の適用
            const comparisonCard = document.getElementById('budgetComparisonCard');
            if (budgetComparison < 0) {
                comparisonCard.classList.add('warning');
            } else {
                comparisonCard.classList.remove('warning');
            }
        }
    }

    // 平均予算の計算
    calculateAverageBudget() {
        if (this.similarProjects.length === 0) return 0;
        const total = this.similarProjects.reduce((sum, project) => sum + project.budget, 0);
        return Math.round(total / this.similarProjects.length);
    }

    // KPIリセット
    resetKPI() {
        document.getElementById('proposedBudgetValue').textContent = '¥0';
        document.getElementById('averageBudgetValue').textContent = '¥0';
        document.getElementById('budgetComparisonValue').textContent = '¥0';
        document.getElementById('similarProjectsValue').textContent = '0件';
        document.getElementById('budgetComparisonCard').classList.remove('warning');
    }

    // 提案予算の更新
    updateProposedBudget(budget) {
        if (budget) {
            document.getElementById('proposedBudgetValue').textContent = `¥${parseInt(budget).toLocaleString()}`;
        } else {
            document.getElementById('proposedBudgetValue').textContent = '¥0';
        }
    }

    // 新規プロジェクト作成
    newProject() {
        document.getElementById('projectForm').reset();
        this.currentProject = null;
        this.similarProjects = [];
        this.resetKPI();
        this.renderProjectsList();
        this.showToast('新規プロジェクトを作成しました', 'info');
    }

    // プロジェクト保存
    saveProject() {
        if (!this.currentProject) {
            this.showToast('保存するプロジェクトがありません', 'error');
            return;
        }

        // 実際の実装ではローカルストレージやサーバーに保存
        localStorage.setItem('savedProject', JSON.stringify(this.currentProject));
        this.showToast('プロジェクトを保存しました', 'success');
    }

    // データ出力
    exportData() {
        if (!this.currentProject) {
            this.showToast('出力するデータがありません', 'error');
            return;
        }

        const exportData = {
            project: this.currentProject,
            similarProjects: this.similarProjects,
            analysisDate: new Date().toISOString()
        };

        const dataStr = JSON.stringify(exportData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `policy_budget_analysis_${new Date().toISOString().split('T')[0]}.json`;
        link.click();

        this.showToast('データを出力しました', 'success');
    }

    // トーストメッセージ表示
    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast ${type} show`;
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // サンプルデータの読み込み
    loadSampleData() {
        this.sampleProjects = [
            {
                id: '1',
                name: '地域活性化デジタル化推進事業',
                year: 2023,
                budget: 50000000,
                rating: 'A',
                description: '地域の小規模事業者のデジタル化を支援し、地域経済の活性化を図る事業',
                outcomes: '参加事業者の売上向上率平均15%、顧客満足度向上'
            },
            {
                id: '2',
                name: '環境配慮型交通システム整備',
                year: 2022,
                budget: 80000000,
                rating: 'B',
                description: '低炭素社会の実現に向けた公共交通システムの整備事業',
                outcomes: 'CO2排出量削減効果あり、一部地域で交通利便性向上'
            },
            {
                id: '3',
                name: '高齢者見守りサービス構築',
                year: 2023,
                budget: 30000000,
                rating: 'A',
                description: 'IoT技術を活用した高齢者の見守りシステムの構築',
                outcomes: '事故防止効果、家族の安心感向上、地域コミュニティ強化'
            },
            {
                id: '4',
                name: '教育ICT環境整備',
                year: 2022,
                budget: 120000000,
                rating: 'C',
                description: '学校のICT環境整備による教育の質向上事業',
                outcomes: '設備導入は完了したが、活用率が低く効果測定が困難'
            },
            {
                id: '5',
                name: '地域防災システム強化',
                year: 2021,
                budget: 45000000,
                rating: 'B',
                description: '地震・津波対策のための地域防災システムの強化',
                outcomes: '避難時間短縮、住民の防災意識向上'
            },
            {
                id: '6',
                name: '文化財デジタルアーカイブ',
                year: 2022,
                budget: 25000000,
                rating: 'D',
                description: '地域の文化財をデジタル化して保存・公開する事業',
                outcomes: '技術的問題により進捗が遅延、予算超過の可能性'
            }
        ];
    }

    // 履歴タブの表示
    showHistoryTab() {
        document.getElementById('projectsList').style.display = 'none';
        document.getElementById('historySection').style.display = 'block';
        this.loadHistory();
    }

    // 履歴タブの非表示
    hideHistoryTab() {
        document.getElementById('historySection').style.display = 'none';
        document.getElementById('projectsList').style.display = 'block';
    }

    // 履歴の読み込み
    async loadHistory() {
        try {
            // フィルター値を取得
            const status = document.getElementById('statusFilter').value;
            const dateFrom = document.getElementById('dateFromFilter').value;
            const dateTo = document.getElementById('dateToFilter').value;
            
            // クエリパラメータを構築
            const params = new URLSearchParams({
                limit: this.historyLimit,
                offset: (this.historyPage - 1) * this.historyLimit
            });
            
            if (status) params.append('status', status);
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            
            // バックエンドAPIから履歴を取得
            const response = await fetch(`http://localhost:5000/logs?${params}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const historyData = await response.json();
            
            // 履歴を表示
            this.renderHistory(historyData.logs);
            
            // ページネーションを更新
            this.updatePagination(historyData.total_count);
            
        } catch (error) {
            console.error('履歴読み込みエラー:', error);
            this.showToast('履歴の読み込みに失敗しました', 'error');
            
            // エラー時は空の履歴を表示
            this.renderHistory([]);
            this.updatePagination(0);
        }
    }

    // 履歴の表示
    renderHistory(logs) {
        const historyList = document.getElementById('historyList');
        
        if (logs.length === 0) {
            historyList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-history"></i>
                    <p>履歴がありません</p>
                </div>
            `;
            return;
        }
        
        historyList.innerHTML = logs.map(log => `
            <div class="history-item ${log.status === 'error' ? 'error' : ''}">
                <div class="history-item-header">
                    <span class="history-item-title">
                        ${log.status === 'success' ? '分析成功' : '分析エラー'}
                    </span>
                    <span class="history-item-date">
                        ${this.formatDate(log.analysis_date)}
                    </span>
                </div>
                
                <div class="history-item-content">
                    <div class="history-item-text truncated">
                        <strong>現状・目的:</strong> ${log.issue_text}
                    </div>
                    <div class="history-item-text truncated">
                        <strong>事業概要:</strong> ${log.summary_text}
                    </div>
                </div>
                
                <div class="history-item-meta">
                    <span>
                        <i class="fas fa-clock"></i>
                        処理時間: ${log.processing_time ? log.processing_time.toFixed(2) + '秒' : 'N/A'}
                    </span>
                    ${log.predicted_budget ? `
                        <span>
                            <i class="fas fa-yen-sign"></i>
                            予測予算: ¥${parseInt(log.predicted_budget).toLocaleString()}
                        </span>
                    ` : ''}
                    ${log.case_count ? `
                        <span>
                            <i class="fas fa-project-diagram"></i>
                            類似事業: ${log.case_count}件
                        </span>
                    ` : ''}
                    ${log.error_message ? `
                        <span>
                            <i class="fas fa-exclamation-triangle"></i>
                            エラー: ${log.error_message}
                        </span>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    // ページネーションの更新
    updatePagination(totalCount) {
        const totalPages = Math.ceil(totalCount / this.historyLimit);
        const pagination = document.getElementById('historyPagination');
        const pageInfo = document.getElementById('pageInfo');
        const prevBtn = document.getElementById('prevPageBtn');
        const nextBtn = document.getElementById('nextPageBtn');
        
        if (totalPages <= 1) {
            pagination.style.display = 'none';
            return;
        }
        
        pagination.style.display = 'flex';
        pageInfo.textContent = `${this.historyPage} / ${totalPages}`;
        
        prevBtn.disabled = this.historyPage <= 1;
        nextBtn.disabled = this.historyPage >= totalPages;
    }

    // 日付のフォーマット
    formatDate(dateString) {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        return date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // 履歴のエクスポート
    async exportHistory() {
        try {
            // フィルター値を取得
            const status = document.getElementById('statusFilter').value;
            const dateFrom = document.getElementById('dateFromFilter').value;
            const dateTo = document.getElementById('dateToFilter').value;
            
            // クエリパラメータを構築
            const params = new URLSearchParams({
                limit: 1000  // 大量データを取得
            });
            
            if (status) params.append('status', status);
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            
            // バックエンドAPIから履歴を取得
            const response = await fetch(`http://localhost:5000/logs?${params}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const historyData = await response.json();
            
            // CSV形式でエクスポート
            const csvContent = this.convertToCSV(historyData.logs);
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `analysis_history_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();
            
            this.showToast('履歴をエクスポートしました', 'success');
            
        } catch (error) {
            console.error('履歴エクスポートエラー:', error);
            this.showToast('履歴のエクスポートに失敗しました', 'error');
        }
    }

    // データをCSV形式に変換
    convertToCSV(logs) {
        const headers = [
            'ID', '分析日時', 'ステータス', '現状・目的', '事業概要', 
            '予測予算', '平均予算', '類似事業件数', '処理時間', 'エラーメッセージ'
        ];
        
        const csvRows = [headers.join(',')];
        
        logs.forEach(log => {
            const row = [
                log.id,
                log.analysis_date,
                log.status,
                `"${log.issue_text.replace(/"/g, '""')}"`,
                `"${log.summary_text.replace(/"/g, '""')}"`,
                log.predicted_budget || '',
                log.average_budget || '',
                log.case_count || '',
                log.processing_time || '',
                log.error_message ? `"${log.error_message.replace(/"/g, '""')}"` : ''
            ];
            csvRows.push(row.join(','));
        });
        
        return csvRows.join('\n');
    }
}

// アプリケーションの初期化
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new PolicyBudgetSimulator();
});

// グローバル関数として公開（HTMLからの呼び出し用）
window.app = app;
