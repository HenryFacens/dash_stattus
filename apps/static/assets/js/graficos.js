Chart.plugins.register({
    afterDraw: function(chart) {
        if (chart.config.type === 'pie') {
            return; // Se o tipo de gráfico for 'pie', saia da função e não faça nada.
        }
        if (chart.config.type === 'line') {
            return; // Se o tipo de gráfico for 'pie', saia da função e não faça nada.
        }
        var ctx = chart.ctx;

        ctx.font = Chart.helpers.fontString(Chart.defaults.global.defaultFontSize, Chart.defaults.global.defaultFontStyle, Chart.defaults.global.defaultFontFamily);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        chart.data.datasets.forEach(function(dataset, i) {
            var meta = chart.getDatasetMeta(i);
            meta.data.forEach(function(bar, index) {
                var data = dataset.data[index];
                ctx.fillText(data, bar._model.x, bar._model.y - 5);
            });
        });
    }
});

function initChartbar($chartElement, labels, data, colors, legend_onoff = true ,legend = 'Sales') {
    var ordersChart = new Chart($chartElement, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: legend,
                data: data,
                backgroundColor: colors, 
                borderColor: colors,  
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: false
                }
            },
            legend: {
                display: legend_onoff,
            },
            tooltips: {
                enabled: false
            }
        }
    });

    $chartElement.data('chart', ordersChart);
}

function initChartpie($chartElement, labels, data, colors,legend_onoff = true,  legend = 'Sales',legend_local = 'bottom') {
    var ordersChart = new Chart($chartElement, {
        type: 'pie',
        data: {
            labels: labels.map(function(label, index) {
                return label + " (" + data[index] + ")";  // Adiciona valores aos rótulos.
            }),
            datasets: [{
                label: legend,
                data: data,
                backgroundColor: colors, 
                borderColor: colors,  
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    display: false  // Remove o eixo Y, pois não é necessário em gráficos de pizza.
                }
            },
            legend: {
                display: legend_onoff,  // Mostra a legenda.
                position: legend_local  // Define a posição da legenda.
            },
            tooltips: {
                enabled: false
            }
        }
    });

    $chartElement.data('chart', ordersChart);
}

function initChartLine($chartElement, labels, datasets, legend_onoff = true) {

    let minValues = datasets.map(dataset => Math.min(...dataset.data.filter(Boolean)));
    let minValue = Math.min(...minValues);

    // Verificar se o elemento já possui um gráfico associado a ele
    let existingChart = $($chartElement).data('chart');

    if (existingChart) {
        // Se já possui, atualizar o gráfico em vez de criar um novo
        existingChart.data.labels = labels;
        existingChart.data.datasets = datasets.map(dataset => ({
            ...dataset,
            fill: false,
            borderWidth: 3
        }));
        existingChart.update();
        return existingChart;
    } else {
        let salesChart = new Chart($chartElement, {
            type: 'line',
            options: {
                scales: {
                    yAxes: [{
                        gridLines: {
                            lineWidth: 3,
                            color: 'gray',
                            zeroLineColor: 'gray'
                        },
                        ticks: {
                            beginAtZero: false,
                            min: minValue - 20,
                            callback: function(value) {
                                if (!(value % 10)) {
                                    return value + ' mca';
                                }
                            }
                        }
                    }]
                },
                tooltips: {
                    callbacks: {
                        label: function(item, data) {
                            var label = data.datasets[item.datasetIndex].label || '';
                            var yLabel = item.yLabel;
                            var content = '';
                            content += label + ": " + yLabel + " mca";
                            return content;
                        }
                    }
                },
                legend: {
                    display: legend_onoff,
                }
            },
            data: {
                labels: labels,
                datasets: datasets.map(dataset => ({
                    ...dataset,
                    fill: false,
                    borderWidth: 3
                }))
            }
        });
        $($chartElement).data('chart', salesChart);
        return salesChart;
    }
}
