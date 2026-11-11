export function App() {
  return (
    <main className="station">
      <div className="station__line" aria-hidden="true" />
      <div>
        <p className="station__location">İzmir, Türkiye</p>
        <h1>Transit Replan Lab</h1>
        <p className="station__description">
          Coordinate two riders after a timetable disruption.
        </p>
        <p className="station__status">Simulation setup in progress</p>
      </div>
    </main>
  )
}
