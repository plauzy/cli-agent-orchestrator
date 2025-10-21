import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import AppLayout from '@cloudscape-design/components/app-layout'
import TopNavigation from '@cloudscape-design/components/top-navigation'
import SideNavigation from '@cloudscape-design/components/side-navigation'
import Dashboard from './pages/Dashboard'
import AgentOrchestration from './pages/AgentOrchestration'
import TaskDelegation from './pages/TaskDelegation'
import ToolDesign from './pages/ToolDesign'
import WorkflowPatterns from './pages/WorkflowPatterns'
import BestPractices from './pages/BestPractices'

function App() {
  const [activeHref, setActiveHref] = useState('/dashboard')

  return (
    <Router>
      <TopNavigation
        identity={{
          href: '/',
          title: 'CLI Agent Orchestrator',
          logo: { src: '', alt: 'CAO' }
        }}
        utilities={[
          {
            type: 'button',
            text: 'Documentation',
            href: 'https://github.com/awslabs/cli-agent-orchestrator',
            external: true
          },
          {
            type: 'menu-dropdown',
            text: 'Settings',
            items: [
              { id: 'settings', text: 'Preferences' },
              { id: 'support', text: 'Support' }
            ]
          }
        ]}
      />

      <AppLayout
        navigation={
          <SideNavigation
            activeHref={activeHref}
            onFollow={event => {
              if (!event.detail.external) {
                event.preventDefault()
                setActiveHref(event.detail.href)
                window.history.pushState({}, '', event.detail.href)
              }
            }}
            items={[
              { type: 'link', text: 'Dashboard', href: '/dashboard' },
              { type: 'divider' },
              {
                type: 'section',
                text: 'Multi-Agent Workflows',
                items: [
                  { type: 'link', text: 'Agent Orchestration', href: '/orchestration' },
                  { type: 'link', text: 'Task Delegation', href: '/delegation' },
                  { type: 'link', text: 'Workflow Patterns', href: '/patterns' }
                ]
              },
              { type: 'divider' },
              {
                type: 'section',
                text: 'Design & Best Practices',
                items: [
                  { type: 'link', text: 'Tool Design Analyzer', href: '/tool-design' },
                  { type: 'link', text: 'Best Practices Guide', href: '/best-practices' }
                ]
              }
            ]}
          />
        }
        content={
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/orchestration" element={<AgentOrchestration />} />
            <Route path="/delegation" element={<TaskDelegation />} />
            <Route path="/patterns" element={<WorkflowPatterns />} />
            <Route path="/tool-design" element={<ToolDesign />} />
            <Route path="/best-practices" element={<BestPractices />} />
          </Routes>
        }
        headerSelector="#header"
        navigationWidth={280}
        toolsHide
      />
    </Router>
  )
}

export default App
