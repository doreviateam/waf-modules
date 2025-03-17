from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class ContactController(http.Controller):
    @http.route(['/submit/contact'], type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def submit_contact(self, **post):
        try:
            # Création d'un enregistrement dans la base de données
            contact_message = request.env['waf.contact.message'].sudo().create({
                'name': post.get('name'),
                'email': post.get('email'),
                'subject': post.get('subject'),
                'message': post.get('message'),
            })
            
            # Envoi de l'email avec les valeurs directement dans le template
            template = request.env.ref('waf_wo3.email_template_contact_form')
            if template:
                template.sudo().send_mail(
                    contact_message.id,
                    force_send=True,
                    email_values={
                        'email_from': 'noreply@example.com',
                        'email_to': 'admin@example.com',
                        'subject': f"Nouveau message de contact: {post.get('subject')}",
                        'body_html': f"""
                            <div style="margin: 0px; padding: 0px;">
                                <p>Bonjour,</p>
                                <p>Un nouveau message a été reçu via le formulaire de contact :</p>
                                <ul>
                                    <li><strong>Nom:</strong> {post.get('name')}</li>
                                    <li><strong>Email:</strong> {post.get('email')}</li>
                                    <li><strong>Sujet:</strong> {post.get('subject')}</li>
                                </ul>
                                <p><strong>Message:</strong></p>
                                <p>{post.get('message')}</p>
                            </div>
                        """
                    }
                )
            
            return request.redirect('/thank-you')
            
        except Exception as e:
            _logger.error("Erreur lors de la soumission du formulaire: %s", str(e))
            return request.redirect('/contact-error')

    @http.route(['/thank-you'], type='http', auth='public', website=True)
    def thank_you(self, **kw):
        return request.render('waf_wo3.contact_thank_you')

    @http.route(['/contact-error'], type='http', auth='public', website=True)
    def contact_error(self, **kw):
        return request.render('waf_wo3.contact_error') 