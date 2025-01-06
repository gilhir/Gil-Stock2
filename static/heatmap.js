let InverseRateILS;
async function getInverseRate() {
    const url = 'https://www.floatrates.com/daily/ils.json';
  
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      const data = await response.json();
  
      // Find the USD currency information
      const usdInfo = data.usd;
  
      if (usdInfo) {
        // Return the inverseRate
        return usdInfo.inverseRate;
      } else {
        throw new Error('USD currency not found');
      }
    } catch (error) {
      console.error('There was a problem with the fetch operation:', error);
    }
  }
  async function inverserateget() {
    InverseRateILS = await getInverseRate();
  }
  inverserateget();
function updateVisualization(stockData) {
    d3.select("#stock-map").select("svg").remove();

    const data = { name: "Stocks", children: [] };
    const aggregatedData = {};

    Object.keys(stockData).forEach(ticker => {
        let entry = stockData[ticker];
        if (entry.weight > 0) {
            aggregatedData[ticker] = {
                name: ticker,
                value: entry.weight,
                percentage_change: entry.percentage_change
            };
        }
    });

    const totalAggregatedWeight = Object.values(aggregatedData).reduce((sum, { value }) => sum + value, 0);
    Object.keys(aggregatedData).forEach(ticker => {
        aggregatedData[ticker].value = aggregatedData[ticker].value / totalAggregatedWeight;
    });

    data.children = Object.values(aggregatedData);
    data.children.sort((a, b) => b.value - a.value);

    const minPercentageChange = Math.min(...data.children.map(d => d.percentage_change));
    const maxPercentageChange = Math.max(...data.children.map(d => d.percentage_change));

    function getColor(percentage_change) {
        if (percentage_change < 0) {
            const colorScale = d3.scaleLinear().domain([minPercentageChange, 0]).range(["darkred", "white"]);
            return colorScale(percentage_change);
        } else {
            const colorScale = d3.scaleLinear().domain([0, maxPercentageChange]).range(["white", "darkgreen"]);
            return colorScale(percentage_change);
        }
    }

    const width = document.getElementById("stock-map").offsetWidth;
    const height = document.getElementById("stock-map").offsetHeight;

    const svg = d3.select("#stock-map")
        .append("svg")
        .attr("width", width)
        .attr("height", height);    

    const root = d3.hierarchy(data).sum(d => d.value);

    d3.treemap().size([width, height]).padding(1)(root);

    const nodes = svg.selectAll("g")
        .data(root.leaves())
        .enter()
        .append("g")
        .attr("transform", d => `translate(${d.x0},${d.y0})`);

    nodes.append("rect")
        .attr("id", d => d.data.name)
        .attr("width", d => d.x1 - d.x0)
        .attr("height", d => d.y1 - d.y0)
        .attr("fill", d => getColor(d.data.percentage_change))
        .attr("stroke", "#fff");

    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(6.5, (d.y1 - d.y0) / 3))
        .text(d => d.data.name)
        .attr("font-size", d => `${Math.max(8, Math.min((d.x1 - d.x0) / 5, (d.y1 - d.y0) / 5))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(19.5, (d.y1 - d.y0) / 2))
        .text(d => `${(d.data.value * 100).toFixed(2)}%`)
        .attr("font-size", d => `${Math.max(3, Math.min((d.x1 - d.y0) / 18, (d.y1 - d.y0) / 18))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(32.5, (d.y1 - d.y0) / 1.5))
        .text(d => `Change: ${d.data.percentage_change.toFixed(2)}%`)
        .attr("font-size", d => `${Math.max(4, Math.min((d.x1 - d.x0) / 8, (d.y1 - d.y0) / 8))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    document.getElementById("legend-min").innerText = `${minPercentageChange.toFixed(2)}%`;
    document.getElementById("legend-max").innerText = `${maxPercentageChange.toFixed(2)}%`;
}

async function loadHeatmap(userId) {
    try {
      const heatmapDataResponse = await fetch(`/heatmap_data/${userId}`);
      const heatmapData = await heatmapDataResponse.json();
      const dailyPerformanceResponse = await fetch(`/stock_performance/${userId}?period=1day`);
      const dailyPerformance = await dailyPerformanceResponse.json();  
      console.log(dailyPerformance)
      updateWidgets(heatmapData, dailyPerformance); 
  
    } catch (error) {
      console.error('Error loading heatmap data:', error);
    }
  }

function updateWidgets(stockData,dailyPerformance) {
    let totalInvested = 0;
    let totalEarned = 0;
    let initialPortfolioValue = 0;
    let currentPortfolioValue = 0;
    let dailychange = 0;
    
    Object.keys(dailyPerformance).forEach(tick => {
        const ent = dailyPerformance[tick];
        const dailypercentage = ent.percentage_change * ent.weight;
        dailychange += dailypercentage;
    });
    
    Object.keys(stockData).forEach(ticker => {
        const entry = stockData[ticker][0];

        const invested = entry.purchase_price * entry.number_of_stocks;
        const earned = entry.current_price * entry.number_of_stocks;
        
        totalInvested += invested;
        totalEarned += earned;
        
        initialPortfolioValue += invested;
        currentPortfolioValue += earned;
    });

    const portfolioFromBeginning = totalInvested > 0 ? ((totalEarned - totalInvested) / totalInvested) * 100 : 0;
    
    const portfolioToday = dailychange ? dailychange : 0;
    document.getElementById("total-invested").innerText = totalInvested.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("total-invested-ILS").innerText = (totalInvested*InverseRateILS).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("total-earned").innerText = totalEarned.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("total-earned-ILS").innerText = (totalEarned*InverseRateILS).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("portfolio-today").innerText = portfolioToday.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("portfolio-today-ILS").innerText = ((portfolioToday/100)*totalEarned*InverseRateILS).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById("portfolio-beginning").innerText = portfolioFromBeginning.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");    
    updateArrow('portfolio-beginning', '#portfolio-beginning + i');
    updateArrow('portfolio-today', '#portfolio-today + i');
}

function fetchStockPerformanceDay(period) {
    fetch(`/stock_performance/${userId}?period=${period}`)
        .then(response => response.json())
        .then(data => {
            return(data);
        })
        .catch(error => {
            console.error('Error fetching stock performance data:', error);
        });
}
function updateArrow(elementId, arrowElement, isPercentage = false) {
    var value = parseFloat(document.getElementById(elementId).innerText);
    var arrow = document.querySelector(arrowElement);
    if (value > 0) {
        arrow.classList.remove('mdi-arrow-down', 'text-danger');
        arrow.classList.add('mdi-arrow-up', 'text-success');
    } else {
        arrow.classList.remove('mdi-arrow-up', 'text-success');
        arrow.classList.add('mdi-arrow-down', 'text-danger');
    }
    var totalInvested = parseFloat(document.getElementById('total-invested').innerText);
    var totalEarned = parseFloat(document.getElementById('total-earned').innerText);
    var currentArrow = document.querySelector('#total-earned + i');
        if (totalEarned > totalInvested) {
            currentArrow.classList.remove('mdi-arrow-down', 'text-danger');
            currentArrow.classList.add('mdi-arrow-up', 'text-success');
        } else {
            currentArrow.classList.remove('mdi-arrow-up', 'text-success');
            currentArrow.classList.add('mdi-arrow-down', 'text-danger');
        }
}