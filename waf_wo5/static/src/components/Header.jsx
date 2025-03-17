/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useState, useEffect } from 'react';

class Header extends Component {
    setup() {
        this.state = useState({
            isScrolled: false,
            isMobileMenuOpen: false
        });

        useEffect(() => {
            const handleScroll = () => {
                this.state.isScrolled = window.scrollY > 100;
            };

            window.addEventListener('scroll', handleScroll, { passive: true });
            return () => window.removeEventListener('scroll', handleScroll);
        }, []);
    }

    toggleMobileMenu() {
        this.state.isMobileMenuOpen = !this.state.isMobileMenuOpen;
    }

    render() {
        return (
            <nav className={`navbar ${this.state.isScrolled ? 'navbar-scrolled' : ''}`}>
                <div className="container">
                    <a className="navbar-brand" href="/">
                        <img src="/waf_wo5/static/src/img/logo.png" alt="Logo" />
                    </a>

                    <button
                        className="navbar-toggler"
                        onClick={() => this.toggleMobileMenu()}
                    >
                        <span className="navbar-toggler-icon"></span>
                    </button>

                    <div className={`collapse navbar-collapse ${this.state.isMobileMenuOpen ? 'show' : ''}`}>
                        <ul className="navbar-nav ms-auto">
                            <li className="nav-item">
                                <a className="nav-link" href="/accueil">Accueil</a>
                            </li>
                            <li className="nav-item">
                                <a className="nav-link" href="/services">Services</a>
                            </li>
                            <li className="nav-item">
                                <a className="nav-link" href="/realisations">Réalisations</a>
                            </li>
                            <li className="nav-item">
                                <a className="nav-link" href="/contact">Contact</a>
                            </li>
                        </ul>
                    </div>
                </div>
            </nav>
        );
    }
}

export default Header; 