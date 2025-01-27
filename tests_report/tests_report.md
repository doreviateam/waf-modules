# Rapport d'exécution des tests

Date d'exécution : 23/01/2025 à 06:59:46


## Module : uom


## Module : onboarding


## Module : resource


## Module : utm


## Module : web_dialog_size


## Module : web_m2x_options


## Module : mail

    self.assertIn(f'{self.env.company.name}, Some Street Name, Some City Name CA 94134, United States',
- ❌ 'YourTestCompany, Some Street Name, Some City Name CA 94134, United States' not found in 'YourTestCompany, Some Street Name, Some City Name  '

## Module : auth_signup


## Module : web


## Module : auth_signup


## Module : mail


## Module : auth_totp_mail


## Module : phone_validation


## Module : product


## Module : rating


## Module : sales_team


## Module : web_notify

- ✅ Vérification : len(users) > 1
- ❌ False is not true

## Module : web_responsive


## Module : hr


## Module : l10n_fr_department


## Module : partner_autocomplete


## Module : portal


## Module : snailmail


## Module : digest


## Module : spreadsheet


## Module : account


## Module : project


## Module : spreadsheet_dashboard


## Module : base_vat


## Module : hr_timesheet


## Module : project_sms


## Module : project_todo


## Module : spreadsheet_account


## Module : sale


## Module : sale_project


## Module : sale_timesheet


## Module : utm


## Module : web_timeline


## Module : mail


## Module : analytic


## Module : auth_totp


## Module : auth_totp_mail


## Module : contacts


## Module : privacy_lookup


## Module : product


## Module : rating


## Module : sales_team


## Module : web_responsive


## Module : hr


## Module : portal


## Module : sms


## Module : auth_totp_portal


## Module : digest


## Module : hr_org_chart


## Module : hr_skills


## Module : payment


## Module : account


## Module : project

- ✅ Vérification : 'href="http://localhost:8069/web/signup', str(mail_partner.body), 'The message link should contain the url to register to the portal'
- ❌ 'href="http://localhost:8069/web/signup' not found in '<br>
            <p>Dear <span>NoUser portal</span>,</p>
            <p><span>OdooBot</span> has invited you to access the following <span>project</span>:</p>
            <br>
            <a style="background-color:#875A7B; padding:10px; text-decoration:none; color:#fff; border-radius:5px; font-size:12px" href="http://localhost:8097/web/signup?db=dorevia_tests&amp;token=0pWUzr3kHHRxtmQUWtTm&amp;redirect=%2Fmail%2Fview%3Fmodel%3Dproject.project%26res_id%3D248"><strong>Open </strong><strong>Portal</strong></a><br>
            <br>
        ' : The message link should contain the url to register to the portal

## Module : spreadsheet_dashboard


## Module : account_edi_ubl_cii


## Module : account_payment


## Module : hr_timesheet


## Module : project_account


## Module : spreadsheet_account


## Module : account_qr_code_sepa


## Module : sale

- ✅ Vérification : so_line_1.price_unit, 50.0
- ❌ 100.0 != 50.0
- ✅ Vérification : order_in_other_currency.amount_total, 960.0
- ❌ 480.0 != 960.0
- ✅ Vérification : order_line.price_unit, 180, "First pricelist rule not applied"
- ❌ 90.0 != 180 : First pricelist rule not applied

## Module : account


## Module : sale


## Module : l10n_fr_fec


## Module : sale_management


## Module : sale_product_configurator


## Module : sale_project


## Module : sale_timesheet


## Module : project


## Module : sale_timesheet


## Module : watergile_partner

- ✅ Vérification : ValidationError:
- ❌ ValidationError not raised
- ✅ Vérification : ValidationError:
- ❌ ValidationError not raised
- ✅ Vérification : self.company_main.department_id, self.company_main.zip_id.department_id

## Résumé

- Total des tests : 0
- Tests réussis : 0
- Tests échoués : 0

