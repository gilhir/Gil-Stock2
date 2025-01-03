function updateVisualization(stockData) {
    // Clear the existing SVG elements
    d3.select("#stock-map").select("svg").remove();
    
    // Prepare the data with aggregated weights
    const data = {
        name: "Stocks",
        children: []
    };

    const aggregatedData = {};

    // Use the stockData directly from the server response
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

    // Calculate total aggregated weight for normalization
    const totalAggregatedWeight = Object.values(aggregatedData).reduce((sum, { value }) => sum + value, 0);

    // Normalize the weights to sum up to 1
    Object.keys(aggregatedData).forEach(ticker => {
        aggregatedData[ticker].value = aggregatedData[ticker].value / totalAggregatedWeight;
    });

    data.children = Object.values(aggregatedData);

    // Sort data by value for left-to-right alignment
    data.children.sort((a, b) => b.value - a.value);

    // Find the min and max percentage_change
    const minPercentageChange = Math.min(...data.children.map(d => d.percentage_change));
    const maxPercentageChange = Math.max(...data.children.map(d => d.percentage_change));

    // Function to get color based on percentage_change
    function getColor(percentage_change) {
        if (percentage_change < 0) {
            const colorScale = d3.scaleLinear()
                .domain([minPercentageChange, 0])
                .range(["darkred", "white"]);
            return colorScale(percentage_change);
        } else {
            const colorScale = d3.scaleLinear()
                .domain([0, maxPercentageChange])
                .range(["white", "darkgreen"]);
            return colorScale(percentage_change);
        }
    }

    // Create the visualization
    const width = 1116;
    const height = 620;

    const svg = d3.select("#stock-map")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const root = d3.hierarchy(data)
        .sum(d => d.value);

    d3.treemap()
        .size([width, height])
        .padding(1)
        (root);

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

    // Add text with horizontal orientation and appropriate font size
    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(6.5, (d.y1 - d.y0) / 3))
        .attr("transform", d => `rotate(0, ${Math.max(5, (d.x1 - d.x0) / 2)}, ${Math.max(6.5, (d.y1 - d.y0) / 3)})`)
        .text(d => d.data.name)
        .attr("font-size", d => `${Math.max(8.45, Math.min((d.x1 - d.x0) / 5.775, (d.y1 - d.y0) / 5.775))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(19.5, (d.y1 - d.y0) / 2))
        .attr("transform", d => `rotate(0, ${Math.max(5, (d.x1 - d.x0) / 2)}, ${Math.max(19.5, (d.y1 - d.y0) / 2)})`)
        .text(d => `${(d.data.value * 100).toFixed(2)}%`)
        .attr("font-size", d => `${Math.max(2.55, Math.min((d.x1 - d.x0) / 18.085, (d.y1 - d.y0) / 18.085))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    nodes.append("text")
        .attr("x", d => Math.max(5, (d.x1 - d.x0) / 2))
        .attr("y", d => Math.max(32.5, (d.y1 - d.y0) / 1.5))
        .attr("transform", d => `rotate(0, ${Math.max(5, (d.x1 - d.x0) / 4)}, ${Math.max(32.5, (d.y1 - d.y0) / 1.5)})`)
        .text(d => `Change: ${d.data.percentage_change.toFixed(2)}%`)
        .attr("font-size", d => `${Math.max(4.55, Math.min((d.x1 - d.x0) / 8.085, (d.y1 - d.y0) / 8.085))}px`)
        .attr("fill", "#000")
        .attr("text-anchor", "middle");

    document.getElementById("legend-min").innerText = `${minPercentageChange.toFixed(2)}%`;
    document.getElementById("legend-max").innerText = `${maxPercentageChange.toFixed(2)}%`;
}
