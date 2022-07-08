from kraken.std.helm import helm_package, helm_push

package = helm_package(chart_path="kraken-example")

helm_push(
    name="helmPublish",
    chart_tarball=package.chart_tarball,
    chart_name="chart.tgz",
    registry_url="https://example.jfrog.io/artifactory/helm-local/kraken-example/",
)
