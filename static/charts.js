const colors = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
    '#FF9F40', '#C9CBCF', '#7BC225', '#1E90FF', '#FF6F61',
    '#8E44AD', '#2ECC71'
];

function getColor(index) {
    return colors[index % colors.length];
}

function hexToRgba(hex, alpha) {
    const sanitized = hex.replace('#', '');
    const bigint = parseInt(sanitized, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function filterSeriesByYear(series, year) {
    if (!year || year === 'ALL') {
        return series;
    }
    return series.filter(point => point.year === year);
}

function setupYearFilter(containerId, years, onSelect) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    const uniqueYears = Array.from(new Set(years || [])).sort();
    const filterYears = ['ALL', ...uniqueYears];

    container.innerHTML = '';

    filterYears.forEach((year, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'year-filter-button';
        button.textContent = year === 'ALL' ? 'All Years' : year;
        if (index === 0) {
            button.classList.add('active');
        }
        button.addEventListener('click', () => {
            container.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            onSelect(year);
        });
        container.appendChild(button);
    });

    onSelect('ALL');
}

function getCutoffChartData(cutoffSeries) {
    return {
        labels: cutoffSeries.map(point => point.date),
        cutoffData: cutoffSeries.map(point => point.crs),
        rollingData: cutoffSeries.map(point => point.rolling_avg),
        invitationData: cutoffSeries.map(point => point.invitations)
    };
}

function updateCutoffChart(chart, cutoffSeries) {
    const { labels, cutoffData, rollingData, invitationData } = getCutoffChartData(cutoffSeries);
    chart.data.labels = labels;
    if (chart.data.datasets[0]) {
        chart.data.datasets[0].data = cutoffData;
    }
    if (chart.data.datasets[1]) {
        chart.data.datasets[1].data = rollingData;
    }
    if (chart.data.datasets[2]) {
        chart.data.datasets[2].data = invitationData;
    }
    chart.update();
}

function getCumulativeChartData(cumulativeSeries) {
    return {
        labels: cumulativeSeries.map(point => point.date),
        drawCounts: cumulativeSeries.map(point => point.draws),
        inviteCounts: cumulativeSeries.map(point => point.invitations)
    };
}

function updateCumulativeDrawsChart(chart, cumulativeSeries) {
    const { labels, drawCounts, inviteCounts } = getCumulativeChartData(cumulativeSeries);
    chart.data.labels = labels;
    if (chart.data.datasets[0]) {
        chart.data.datasets[0].data = drawCounts;
    }
    if (chart.data.datasets[1]) {
        chart.data.datasets[1].data = inviteCounts;
    }
    chart.update();
}

function createYearlyDrawsChart(ctx, years, yearlyDraws) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: years,
            datasets: [{
                label: 'Total Draws',
                data: yearlyDraws,
                backgroundColor: '#FF6384',
                borderRadius: 8,
                borderSkipped: false,
                barPercentage: 0.7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 20,
                    bottom: 20
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 20,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        display: true,
                        drawBorder: false,
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createMonthlyDrawsChart(ctx, years, monthlyData) {
    const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const monthKeys = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, '0'));

    const datasets = years.map((year, index) => ({
        label: year,
        data: monthKeys.map(monthKey => (monthlyData[monthKey] && monthlyData[monthKey][year]) || 0),
        backgroundColor: hexToRgba(getColor(index), 0.85),
        borderColor: getColor(index),
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.8,
        categoryPercentage: 0.75,
        stack: 'monthly_distribution'
    }));

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthLabels,
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 20,
                    bottom: 20
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createProgramMixChart(ctx, years, programInviteData) {
    const programNames = Array.from(
        years.reduce((set, year) => {
            const entries = programInviteData[year] || {};
            Object.keys(entries).forEach(name => set.add(name));
            return set;
        }, new Set())
    ).sort();

    const totalsByYear = years.reduce((acc, year) => {
        const entries = programInviteData[year] || {};
        acc[year] = Object.values(entries).reduce((sum, value) => sum + value, 0);
        return acc;
    }, {});

    const datasets = programNames.map((program, index) => ({
        label: program,
        data: years.map(year => {
            const total = totalsByYear[year] || 0;
            if (!total) {
                return 0;
            }
            const invitations = (programInviteData[year] && programInviteData[year][program]) || 0;
            return Number(((invitations / total) * 100).toFixed(2));
        }),
        borderColor: getColor(index),
        backgroundColor: hexToRgba(getColor(index), 0.35),
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        stack: 'program_mix'
    }));

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: years,
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 16,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: context => `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        callback: value => `${value}%`,
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createProgramDistributionChart(ctx, years, programData) {
    const programTypes = [
        'Agriculture and agri-food occupations (Version 1)',
        'Canadian Experience Class',
        'Federal Skilled Trades',
        'Federal Skilled Worker',
        'French language proficiency (Version 1)',
        'General',
        'Healthcare occupations (Version 1)',
        'No Program Specified',
        'Provincial Nominee Program',
        'STEM occupations (Version 1)',
        'Trade occupations (Version 1)',
        'Transport occupations (Version 1)'
    ];

    const datasets = programTypes.map((program, index) => ({
        label: program,
        data: years.map(year => programData[year]?.[program] || 0),
        backgroundColor: getColor(index),
        borderColor: getColor(index),
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.8,
        categoryPercentage: 0.9
    }));

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: years,
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 20,
                    bottom: 20
                }
            },
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createCutoffTrendChart(ctx, cutoffSeries) {
    const { labels, cutoffData, rollingData, invitationData } = getCutoffChartData(cutoffSeries);
    return new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'line',
                    label: 'CRS Cut-off',
                    data: cutoffData,
                    borderColor: getColor(0),
                    backgroundColor: getColor(0),
                    fill: false,
                    tension: 0.25,
                    pointRadius: 2,
                    yAxisID: 'y',
                    spanGaps: true
                },
                {
                    type: 'line',
                    label: '5-Draw Rolling Avg',
                    data: rollingData,
                    borderColor: getColor(3),
                    backgroundColor: getColor(3),
                    fill: false,
                    tension: 0.25,
                    borderDash: [6, 4],
                    pointRadius: 0,
                    yAxisID: 'y',
                    spanGaps: true
                },
                {
                    type: 'bar',
                    label: 'Invitations',
                    data: invitationData,
                    backgroundColor: hexToRgba(getColor(1), 0.45),
                    borderColor: getColor(1),
                    borderWidth: 1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 16,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 12,
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    },
                    beginAtZero: true,
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createCumulativeDrawsChart(ctx, cumulativeSeries) {
    const { labels, drawCounts, inviteCounts } = getCumulativeChartData(cumulativeSeries);

    return new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'line',
                    label: 'Cumulative Draws',
                    data: drawCounts,
                    borderColor: getColor(4),
                    backgroundColor: getColor(4),
                    fill: false,
                    tension: 0,
                    stepped: 'middle',
                    yAxisID: 'y'
                },
                {
                    type: 'line',
                    label: 'Cumulative Invitations',
                    data: inviteCounts,
                    borderColor: getColor(5),
                    backgroundColor: hexToRgba(getColor(5), 0.25),
                    fill: true,
                    tension: 0.25,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 16,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 12,
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}

function createScoreChart(ctx, scoreData) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: scoreData.dates,
            datasets: scoreData.programs.map((program, index) => ({
                label: program.name,
                data: program.scores,
                borderColor: getColor(index),
                backgroundColor: getColor(index),
                fill: false,
                tension: 0.4,
                spanGaps: true
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        font: {
                            family: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                        }
                    }
                }
            }
        }
    });
}
